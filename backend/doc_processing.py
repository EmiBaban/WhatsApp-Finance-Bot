from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import os
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import base64
import pytesseract
import json
from PyPDF2 import PdfReader
import re
from prompts import get_receipt_analysis_prompt, get_pdf_analysis_prompt, get_financial_command_prompt, get_period_parse_prompt
from datetime import datetime, timedelta, timezone

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def get_normalized_mapping(supabase_client):
    """Obține dicționare cu forma corectă a numelor de companii și bănci (pt. normalizare)."""
    result = supabase_client.table("Accounts").select("compania,banca").execute()
    company_mapping = {}
    bank_mapping = {}
    
    for row in result.data or []:
        # Normalizare companii
        if row.get("compania"):
            original = row["compania"]
            normalized = original.lower().replace(" ", "", "_")
            company_mapping[normalized] = original
        
        # Normalizare bănci
        if row.get("banca"):
            original = row["banca"]
            normalized = original.lower().replace(" ", "", "_")
            bank_mapping[normalized] = original
    
    return company_mapping, bank_mapping



def mask_iban(iban: str) -> str:
    s = re.sub(r'\s+', '', iban)
    if len(s) <= 8: 
        return s
    return f"{s[:6]}…{s[-4:]}"

def save_pending_action(supabase, profile_name, action_type, payload: dict):
    # opțional: șterge pending vechi ca să fie unul singur / user
    supabase.table("Pending_Actions").delete().eq("profile_name", profile_name).execute()
    return supabase.table("Pending_Actions").insert({
        "profile_name": profile_name,
        "action_type": action_type,
        "payload": payload
    }).execute()

def get_pending_action(supabase, profile_name):
    # ia cel mai recent pending pt user
    resp = supabase.table("Pending_Actions")\
        .select("*").eq("profile_name", profile_name)\
        .order("created_at", desc=True).limit(1).execute()
    return resp.data[0] if resp.data else None

def clear_pending_action(supabase, profile_name):
    supabase.table("Pending_Actions").delete().eq("profile_name", profile_name).execute()

def present_candidates_message(alias, candidates):
    lines = [f"Am găsit mai multe conturi pentru «{alias}». Alege varianta:"]
    for i, c in enumerate(candidates, start=1):
        iban = c["iban"]
        banca = c.get("banca", "")
        compania = c.get("compania", "")
        
        # Prescurtări bănci pentru claritate
        bank_short = {
            "Banca Transilvania": "BT",
            "BCR": "BCR", 
            "BRD": "BRD",
            "ING Bank": "ING",
            "Raiffeisen Bank": "Raiffeisen",
            "UniCredit Bank": "UniCredit",
            "CEC Bank": "CEC",
            "Alpha Bank": "Alpha",
            "OTP Bank": "OTP",
            "First Bank": "First",
            "Libra Internet Bank": "Libra",
            "Vista Bank": "Vista",
            "Patria Bank": "Patria",
            "Garanti BBVA": "Garanti",
            "Intesa Sanpaolo Bank": "Intesa",
            "TBI Bank": "TBI",
            "Exim Banca Românească": "Exim"
        }.get(banca, banca)
        
        description = f"{bank_short} {compania}".strip() or "cont"
        lines.append(f"{i}) {description} — {mask_iban(iban)}")
    lines.append("Răspunde cu *1* sau *2* … ori trimite IBAN-ul complet.")
    return "\n".join(lines)

def present_candidates_message_with_all(alias, candidates):
    lines = [f"Am găsit mai multe conturi pentru «{alias}». Alege varianta:"]
    zws = "\u200B"  # zero-width space pentru a evita auto-list formatting
    lines.append(f"{zws}0) Toate conturile")
    for i, c in enumerate(candidates, start=1):
        iban = c["iban"]
        banca = c.get("banca", "")
        compania = c.get("compania", "")
        
        # Prescurtări bănci pentru claritate
        bank_short = {
            "Banca Transilvania": "BT",
            "BCR": "BCR", 
            "BRD": "BRD",
            "ING Bank": "ING",
            "Raiffeisen Bank": "Raiffeisen",
            "UniCredit Bank": "UniCredit",
            "CEC Bank": "CEC",
            "Alpha Bank": "Alpha",
            "OTP Bank": "OTP",
            "First Bank": "First",
            "Libra Internet Bank": "Libra",
            "Vista Bank": "Vista",
            "Patria Bank": "Patria",
            "Garanti BBVA": "Garanti",
            "Intesa Sanpaolo Bank": "Intesa",
            "TBI Bank": "TBI",
            "Exim Banca Românească": "Exim"
        }.get(banca, banca)
        
        description = f"{bank_short} {compania}".strip() or "cont"
        lines.append(f"{zws}{i}) {description} — {mask_iban(iban)}")
    lines.append("Răspunde cu *0* pentru toate conturile, *1* sau *2* … ori trimite IBAN-ul complet.")
    return "\n".join(lines)


def compute_spent_sum(supabase_client, start_iso: str, end_iso: str, iban: str | None = None):
    """Calculează totalul cheltuit (sumă pozitivă) în intervalul dat. Folosește valorile negative din `amount`."""
    q = supabase_client.table("Transactions").select("amount,account,created_at").gte("created_at", start_iso).lte("created_at", end_iso)
    if iban:
        q = q.eq("account", iban)
    resp = q.execute()
    total_neg = 0.0
    for row in resp.data or []:
        try:
            amt = float(row.get("amount") or 0)
            if amt < 0:
                total_neg += amt
        except Exception:
            continue
    return round(-total_neg, 2)


# functie care extrage textul din audio
def extract_audio_text(r, client):
    """
    Descarcă un fișier audio de la Twilio și returnează textul transcris cu OpenAI.
    """
    try:
        if r.status_code != 200:
            return f"❌ Eroare descărcare audio: {r.status_code}"

        # Detectăm tipul fișierului
        content_type = r.headers.get("Content-Type", "").lower()
        ext = "ogg" if "ogg" in content_type else (
              "wav" if "wav" in content_type else (
              "mp3" if "mpeg" in content_type else None))

        if not ext:
            return f"❌ Format audio nesuportat: {content_type}"

        # Punem în BytesIO pentru a nu salva pe disk
        audio_bytes = BytesIO(r.content)

        # Trimitem la OpenAI pentru transcriere
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(f"voice.{ext}", audio_bytes)
        )

        return transcript.text.strip()

    except Exception as e:
        return f"❌ Eroare la procesarea audio: {str(e)}"


def encode_image(image_path):
    """Codifică imaginea în base64 pentru OpenAI."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def process_pdf(ext, sender, message, r, client, supabase_client):
    pdf_reader = PdfReader(BytesIO(r.content))
    text_from_pdf = ""
    
    for page in pdf_reader.pages:
        text_from_pdf += page.extract_text() + "\n"

    result = {
        "success": False,
        "message": "",
        "text_from_img": "",
        "response": "",
        "error": None
    }

    # Obține conținutul imaginii
    username = sender.split(":")[1] if ":" in sender else "unknown"

    # Obține promptul pentru analiza PDF
    prompt = get_pdf_analysis_prompt(text_from_pdf, sender, message)

    # Codifică și trimite la OpenAI
    try:
        gpt_response = client.responses.create(
            model="gpt-5",
            input=prompt,
        )

        json_text = gpt_response.output_text

        try:
            # incarca datele in format json
            data = json.loads(json_text)
            print(data)
            # insereaza datele in tabela de tranzactii
            response = supabase_client.table("Transactions").insert(data).execute()

            # selecteaza toate sumele din tabela accounts si opreste doar pe ultima
            account_sum_response = supabase_client.table("Accounts").select("sum").execute()
            account_sum = account_sum_response.data[-1]["sum"]

            # construire raspuns twilio
            twilio_response = f"✅ Tranzacție salvată: {data.get('amount')} RON. Sold curent: {account_sum} RON"
            print(response)
            print(twilio_response)
        except Exception as e:
            print("eroare")
            print(e)

    except Exception as e:
        print("eroare2")
        result["error"] = f"Eroare la apelul OpenAI: {str(e)}"
        return result
    
    return twilio_response


# import cv2
# import numpy as np
from PIL import Image

# def preprocess_for_ocr(filename):
#     """
#     Îmbunătățește imaginea înainte de OCR:
#     - convertește la grayscale
#     - crește contrastul
#     - aplică binarizare adaptivă
#     - face un mic blur pentru a reduce zgomotul
#     """
#     img = cv2.imread(filename, cv2.IMREAD_COLOR)
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

#     # eliminare zgomot ușor
#     gray = cv2.medianBlur(gray, 3)

#     # creștere contrast
#     gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)

#     # binarizare adaptivă (separa textul de fundal)
#     thresh = cv2.adaptiveThreshold(
#         gray, 255,
#         cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
#         cv2.THRESH_BINARY,
#         31, 5
#     )

#     # eventual deskew (dacă textul e înclinat)
#     coords = np.column_stack(np.where(thresh > 0))
#     angle = cv2.minAreaRect(coords)[-1]
#     if angle < -45:
#         angle = -(90 + angle)
#     else:
#         angle = -angle

#     (h, w) = thresh.shape[:2]
#     M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
#     deskewed = cv2.warpAffine(thresh, M, (w, h),
#                               flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
#     cv2.imwrite(filename.replace(".jpg", "_proc.jpg"), deskewed)
#     return deskewed


# functie de procesare a imaginii, extragerea textului cu tesseract OCR
def process_image(ext, sender, message, r, client, supabase_client):
    """
    Procesează imaginea unei facturi, extrage date, generează SQL și inserează în Supabase.
    Returnează un dicționar cu rezultatele.
    
    Args:
        message: poate conține indicații despre contul destinație (ex: "contul bcr")
    """
    result = {
        "success": False,
        "message": "",
        "text_from_img": "",
        "response": "",
        "error": None
    }

    # Obține conținutul imaginii
    # content_type = r.headers.get("Content-Type", "").lower()
    username = sender.split(":")[1] if ":" in sender else "unknown"

    # Creează director și salvează imaginea
    user_dir = f"uploads/{username}"
    os.makedirs(user_dir, exist_ok=True)
    filename = f"{user_dir}/{message or 'image'}.{ext}"
    with open(filename, "wb") as f:
        f.write(r.content)

    # Extrage textul din imagine (opțional, pentru verificare)
    img = Image.open(filename)
    text_from_img = pytesseract.image_to_string(img, lang="ron+eng")
    # processed = preprocess_for_ocr(filename)
    # text_from_img = pytesseract.image_to_string(processed, lang="ron+eng")

    print("Extracted text from img:", text_from_img)
    result["text_from_img"] = text_from_img

    # Extrage indicații despre contul destinație din mesajul text
    account_hint = None
    if message and isinstance(message, str):
        # Obține maparea normalizată a băncilor
        _, bank_mapping = get_normalized_mapping(supabase_client)
        
        # Caută mențiuni despre cont în text (ex: "contul bcr" sau "în ing")
        lower_msg = message.lower()
        if "cont" in lower_msg or "în" in lower_msg or "in" in lower_msg:
            for normalized_bank, original_bank in bank_mapping.items():
                if normalized_bank in lower_msg.replace(" ", ""):
                    account_hint = original_bank
                    break

    # Obține promptul pentru analiza bonului fiscal
    prompt = get_receipt_analysis_prompt(text_from_img, sender, account_hint, message)

    # Codifică și trimite la OpenAI
    try:
        base64_image = encode_image(filename)
        # client = OpenAI(api_key=openai_key)
        gpt_response = client.responses.create(
            model="gpt-5",
            input=prompt,
        )

        json_text = gpt_response.output_text
        print("GPT response:", json_text)

        try:
            data = json.loads(json_text)
            
            # Aplică sugestia de cont din mesajul text dacă există și dacă contul nu e detectat în imagine
            if account_hint and (not data.get('account') or data['account'] == 'null'):
                # Caută IBAN-ul pentru banca sugerată
                resp = supabase_client.table("Accounts").select("iban").eq("banca", account_hint).execute()
                if resp.data:
                    data['account'] = resp.data[0]['iban']
                    print(f"💡 Using suggested bank account: {data['account']} ({account_hint})")
            
            # Inserează tranzacția în baza de date
            response = supabase_client.table("Transactions").insert(data).execute()
            account_sum_response = supabase_client.table("Accounts").select("sum").execute()
            account_sum = account_sum_response.data[-1]["sum"]
            
            # Construiește mesajul de răspuns
            bank_info = ""
            if account_hint:
                bank_info = f" în contul {account_hint}"
            twilio_response = f"✅ Tranzacție salvată{bank_info}: {data.get('amount')} RON. Sold curent: {account_sum} RON"
            print(response)
            print(twilio_response)
            
        except Exception as e:
            print("eroare")
            print(e)
            return f"❌ Eroare la procesarea tranzacției: {str(e)}"

    except Exception as e:
        print("eroare2")
        result["error"] = f"Eroare la apelul OpenAI: {str(e)}"
        return result

    return twilio_response


import json

def execute_db_action(supabase_client, json_text):
    """
    Primește o acțiune în format JSON (generată de GPT din input-ul utilizatorului)
    și o execută pe baza de date Supabase.

    Parametri:
        supabase_client: conexiunea activă la Supabase
        json_text (str): un JSON cu următoarea structură:
            {
                "operation": "update" | "select",
                "table": "Accounts",
                "data": {...},          # doar pentru update
                "conditions": {...}     # filtre WHERE pentru update/select
            }

    Returnează:
        dict cu cheia "status" sau "error" și, dacă e succes, și cheia "response".
    """

    # Parsăm textul JSON într-un obiect Python (dict)
    action = json.loads(json_text)

    # Extragem câmpurile principale din JSON
    operation = action.get("operation")   # ce tip de operație facem: update/select
    table = action.get("table")           # tabelul pe care lucrăm (ex: "Accounts")
    data = action.get("data")             # ce date vrem să modificăm (pentru update)
    conditions = action.get("conditions") # condițiile WHERE (ex: {"iban": "RO..."} )

    try:
        # -----------------------------------------
        # OPERAȚIA DE UPDATE
        # -----------------------------------------
        if operation == "update":
            # Dacă lipsesc data sau conditions, nu putem face update
            if not data or not conditions:
                return {"error": "Missing data or conditions for update."}

            updates = {}
            for k, v in data.items():
                # Verificăm dacă valoarea este un increment (ex: {"sum": {"increment": 100}})
                if isinstance(v, dict) and "increment" in v:
                    account = conditions.get("iban")

                    # Citim valoarea curentă din DB pentru câmpul respectiv
                    current_resp = supabase_client.table(table).select(k).eq("iban", account).execute()
                    current_val = current_resp.data[0][k] if current_resp.data else 0

                    # Aplicăm incrementul
                    updates[k] = current_val + v["increment"]
                else:
                    # Altfel, doar suprascriem câmpul cu valoarea dată
                    updates[k] = v

            # Facem UPDATE în Supabase cu noile valori
            response = supabase_client.table(table).update(updates).eq(
                list(conditions.keys())[0],   # coloana de filtrare (ex: "iban")
                list(conditions.values())[0]  # valoarea de filtrare (ex: "RO...")
            ).execute()

            return {"status": "success", "response": response}

        # -----------------------------------------
        # OPERAȚIA DE SELECT
        # -----------------------------------------
        elif operation == "select":
            account = conditions.get("iban") if conditions else None
            if not account:
                return {"error": "Missing conditions for select."}

            # Interogăm contul cu IBAN-ul specificat
            resp = supabase_client.table(table).select("*").eq("iban", account).execute()
            return {"status": "success", "response": resp}

        # -----------------------------------------
        # OPERAȚII NESUPORTATE
        # -----------------------------------------
        else:
            return {"error": f"Operation '{operation}' not supported."}

    # Dacă apare o excepție, returnăm un mesaj de eroare prietenos
    except Exception as e:
        return {"error": str(e)}

   
# functie care raspunde la mesaje de tipul: adauga bani in contul X, cati bani am in contul X
def get_all_account_balances(supabase_client):
    """Obține soldurile pentru toate conturile din baza de date."""
    try:
        # Obține toate conturile din baza de date
        result = supabase_client.table("Accounts").select("*").execute()
        
        if not result.data:
            return "❌ Nu există conturi în baza de date."
        
        # Construiește mesajul cu soldurile
        lines = ["📊 Soldurile pentru toate conturile:"]
        total_balance = 0.0
        
        for i, account in enumerate(result.data, 1):
            iban = account.get("iban", "")
            banca = account.get("banca", "")
            compania = account.get("compania", "")
            sum_value = account.get("sum", 0.0)
            
            # Formatează numele contului
            if banca and compania:
                account_name = f"{banca} - {compania}"
            elif banca:
                account_name = banca
            elif compania:
                account_name = compania
            else:
                account_name = "Cont necunoscut"
            
            # Formatează IBAN-ul (primele 4 și ultimele 4 caractere)
            if len(iban) > 8:
                masked_iban = f"{iban[:4]}...{iban[-4:]}"
            else:
                masked_iban = iban
            
            # Adaugă linia cu soldul
            lines.append(f"  {i}. {account_name}")
            lines.append(f"     IBAN: {masked_iban}")
            lines.append(f"     Sold: {sum_value:.2f} RON")
            lines.append("")
            
            total_balance += sum_value
        
        # Adaugă totalul
        lines.append(f"💰 Total general: {total_balance:.2f} RON")
        
        return "\n".join(lines)
        
    except Exception as e:
        print(f"Error getting all balances: {e}")
        return "❌ Eroare la obținerea soldurilor pentru toate conturile."

def answer_request(message, profile_name, client, supabase_client):
    import json, re

    def get_normalized_mapping(supabase_client):
        """Obține dicționare cu forma corectă a numelor de companii și bănci (pt. normalizare)."""
        result = supabase_client.table("Accounts").select("compania,banca").execute()
        company_mapping = {}
        bank_mapping = {}
        
        for row in result.data or []:
            # Normalizare companii
            if row.get("compania"):
                original = row["compania"]
                normalized = original.lower().replace(" ", "")
                company_mapping[normalized] = original
            
            # Normalizare bănci
            if row.get("banca"):
                original = row["banca"]
                normalized = original.lower().replace(" ", "")
                bank_mapping[normalized] = original
        
        return company_mapping, bank_mapping

    def _find_account_candidates(conditions: dict):
        """
        Returnează liste de candidați în formatul așteptat de try_resolve_pending:
        [{"iban","banca","compania"}]
        """
        conditions = conditions or {}
        candidates = []

        # 1) IBAN direct (cel mai sigur)
        iban = (conditions.get("iban") or "").replace(" ", "").upper()
        if iban:
            res = supabase_client.table("Accounts").select("iban, banca, compania").eq("iban", iban).execute()
            for r in res.data or []:
                candidates.append({
                    "iban": r["iban"],
                    "banca": r.get("banca"),
                    "compania": r.get("compania")
                })
            return candidates

        # 2) Filtrare după banca/compania (dacă le avem)
        q = supabase_client.table("Accounts").select("iban,banca,compania")
        if conditions.get("banca"):
            q = q.eq("banca", conditions["banca"])
        if conditions.get("compania"):
            q = q.eq("compania", conditions["compania"])
        res = q.execute()
        for r in res.data or []:
            candidates.append({
                "iban": r["iban"],
                "banca": r.get("banca"),
                "compania": r.get("compania")
            })
        return candidates

    # === Ramură generică: "cât am cheltuit [perioadă?]" ===
    normalized_msg = (message or "").lower()
    if re.search(r"c(â|a)t\s+am\s+cheltuit", normalized_msg):
        # 1) Parsează perioada cu LLM
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        period_prompt = get_period_parse_prompt(message, now_iso)
        try:
            period_resp = client.responses.create(model="gpt-5-mini", input=period_prompt)
            period_json_text = period_resp.output_text.strip()
            period_obj = json.loads(period_json_text)
            start_iso = period_obj.get("start_iso")
            end_iso = period_obj.get("end_iso")
            confidence = float(period_obj.get("confidence") or 0)
        except Exception as e:
            print("⚠️ Eroare la parsarea perioadei:", str(e))
            start_iso = end_iso = None
            confidence = 0

        if not start_iso or not end_iso or confidence < 0.5:
            return "❓ Pentru ce perioadă vrei să calculez? (ex: azi, ieri, ultimele 7 zile, săptămâna trecută, între 2025-01-05 și 2025-02-07)"

        # 2) Identifică eventuale indicii de cont (bancă/companie) din mesaj
        conditions_guess = {}
        company_mapping, bank_mapping = get_normalized_mapping(supabase_client)
        joined = normalized_msg.replace(" ", "")
        for normalized_bank, original_bank in bank_mapping.items():
            if normalized_bank in joined:
                conditions_guess["banca"] = original_bank
                break
        for normalized_company, original_company in company_mapping.items():
            if normalized_company in joined:
                conditions_guess["compania"] = original_company
                break

        candidates = _find_account_candidates(conditions_guess)
        if not candidates:
            return "❌ Nu am găsit conturi potrivite pentru această întrebare."

        # 3) Dacă un singur cont → calc direct; altfel pending cu 0) Toate
        if len(candidates) == 1:
            total = compute_spent_sum(supabase_client, start_iso, end_iso, candidates[0]["iban"])
            return f"💸 Ai cheltuit {total:.2f} RON în perioada selectată ({mask_iban(candidates[0]['iban'])})."

        save_pending_action(supabase_client, profile_name, "sum_spent", {
            "period": "custom",
            "start_iso": start_iso,
            "end_iso": end_iso,
            "candidates": candidates
        })
        return present_candidates_message_with_all("cont", candidates)

    # === PROMPT GPT (rămâne al tău) ===
    prompt = get_financial_command_prompt(message)
    gpt_response = client.responses.create(model="gpt-5-mini", input=prompt)
    json_text = gpt_response.output_text.strip()
    print("🤖 Răspuns GPT:", json_text)

    # === Post-procesare + normalizare companie și bancă ===
    try:
        action = json.loads(json_text)
        company_mapping, bank_mapping = get_normalized_mapping(supabase_client)

        if "conditions" in action:
            # Normalizare companie
            if "compania" in action["conditions"]:
                requested_company = action["conditions"]["compania"].lower().replace(" ", "")
                if requested_company in company_mapping:
                    action["conditions"]["compania"] = company_mapping[requested_company]
                    print("🔄 Nume companie normalizat:", action["conditions"]["compania"])

            # Normalizare bancă
            if "banca" in action["conditions"]:
                requested_bank = action["conditions"]["banca"].lower().replace(" ", "")
                if requested_bank in bank_mapping:
                    action["conditions"]["banca"] = bank_mapping[requested_bank]
                    print("🔄 Nume bancă normalizat:", action["conditions"]["banca"])

            json_text = json.dumps(action)
            
    except Exception as e:
        print("⚠️ Eroare la normalizarea numelor:", str(e))
        # Dacă parsing-ul a eșuat, nu avem ce salva în pending
        try:
            action = json.loads(json_text)
        except Exception:
            return "❌ Nu am înțeles cererea. Poți reformula?"

    # === AICI adăugăm logica operațiilor ===
    op = (action.get("operation") or "none").lower()
    if op not in ("update", "select"):
        return "❌ Nu am înțeles ce operație dorești."

    conditions = action.get("conditions") or {}
    data = action.get("data") or {}

    # Branch UPDATE -> inserăm în Transactions (trigger actualizează Accounts)
    if op == "update":
        try:
            inc = data.get("sum")
            if isinstance(inc, dict):
                if "increment" in inc:
                    amount_val = float(inc["increment"])
                elif "decrement" in inc:
                    amount_val = -float(inc["decrement"])  # fallback
                else:
                    return "❌ Lipsesc detaliile sumei."
            elif isinstance(inc, (int, float)):
                amount_val = float(inc)
            else:
                return "❌ Nu am înțeles suma pentru tranzacție."
        except Exception as e:
            print("Eroare la extragerea sumei:", str(e))
            return "❌ Nu am înțeles suma pentru tranzacție."

        currency = "RON"
        candidates = _find_account_candidates(conditions)
        if not candidates:
            search_term = conditions.get("iban") or conditions.get("compania") or conditions.get("banca") or "contul cerut"
            return f"❌ Nu găsesc niciun cont pentru «{search_term}». Trimite IBAN-ul sau un indiciu mai clar (bancă + companie)."

        if len(candidates) > 1:
            search_term = conditions.get("iban") or (f"{conditions.get('banca','')} {conditions.get('compania','')}".strip()) or "cont"
            save_pending_action(supabase_client, profile_name, "add_trx", {
                "search_term": search_term,
                "amount": amount_val,
                "currency": currency,
                "invoice_number": None,
                "candidates": candidates,
                "description": data.get("description")  # Include description in pending action
            })
            return present_candidates_message(search_term, candidates)

        # Un singur candidat → insert direct
        target_iban = candidates[0]["iban"]
        trx = {
            "amount": float(amount_val),
            "currency": currency,
            "invoice_number": None,
            "profile_name": profile_name or "unknown",
            "account": target_iban,
            "description": data.get("description")  # Include description from GPT
        }
        try:
            supabase_client.table("Transactions").insert(trx).execute()
            
            # Obținem soldul contului pentru a-l afișa în confirmare
            try:
                balance_result = supabase_client.table("Accounts").select("sum").eq("iban", target_iban).single().execute()
                if balance_result.data:
                    current_balance = balance_result.data["sum"]
                    return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({mask_iban(target_iban)}). Sold curent: {current_balance:.2f} RON."
                else:
                    return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({mask_iban(target_iban)})."
            except Exception as balance_error:
                print(f"Error getting balance: {balance_error}")
                return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({mask_iban(target_iban)})."
        except Exception as e:
            print("⚠️ Eroare la insert Transactions (update-flow):", str(e))
            return f"❌ Eroare la salvarea tranzacției: {str(e)}"

    # Branch SELECT (sold)
    # dacă e select, continuăm ca înainte
    if not conditions.get("iban"):
        # Verifică dacă utilizatorul întreabă despre "toate conturile"
        if (not conditions.get("banca") and not conditions.get("compania") and 
            ("toate" in message.lower() or "toate conturile" in message.lower() or 
             "soldul din toate" in message.lower() or "soldurile" in message.lower())):
            # Returnează soldurile pentru toate conturile
            return get_all_account_balances(supabase_client)
        
        candidates = _find_account_candidates(conditions)
        if not candidates:
            search_term = conditions.get("iban") or conditions.get("compania") or conditions.get("banca") or "contul cerut"
            return f"❌ Nu găsesc niciun cont pentru «{search_term}». Trimite IBAN-ul sau un indiciu mai clar (bancă + companie)."
        if len(candidates) > 1:
            search_term = conditions.get("iban") or (f"{conditions.get('banca','')} {conditions.get('compania','')}".strip()) or "cont"
            save_pending_action(supabase_client, profile_name, op, {
                "search_term": search_term,
                "amount": None,
                "currency": "RON",
                "candidates": candidates
            })
            return present_candidates_message(search_term, candidates)
        conditions["iban"] = candidates[0]["iban"]
        action["conditions"] = conditions
        json_text = json.dumps(action)

    result = execute_db_action(supabase_client, json_text)

    # Răspuns pentru SELECT (sold)
    if result.get("status") == "success" and "response" in result:
        response = result["response"]
        if response.data:
            account_info = response.data[0]
            sum_value = account_info.get("sum")
            account = account_info.get("iban")
            print(f"💰 Soldul contului {account} este {sum_value} RON")
            return f"📊 Sold cont: {sum_value} RON ({account})"
        else:
            print("⚠️ Nu există date disponibile.")
            return "⚠️ Nu există date disponibile."
    else:
        # Dacă operația a fost UPDATE reușit, inserăm și o tranzacție text-only
        if (result.get("status") == "success") and (op == "update"):
            try:
                trx = {
                    "amount": float(amount_val) if amount_val is not None else 0.0,
                    "currency": currency,
                    "invoice_number": None,
                    "profile_name": profile_name or "unknown",
                    "account": conditions.get("iban"),
                    "description": data.get("data", {}).get("description")  # Include description from GPT
                }
                supabase_client.table("Transactions").insert(trx).execute()
                # Obținem soldul contului pentru a-l afișa în confirmare
                try:
                    balance_result = supabase_client.table("Accounts").select("sum").eq("iban", trx['account']).single().execute()
                    if balance_result.data:
                        current_balance = balance_result.data["sum"]
                        return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({trx['account']}). Sold curent: {current_balance:.2f} RON."
                    else:
                        return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({trx['account']})."
                except Exception as balance_error:
                    print(f"Error getting balance: {balance_error}")
                    return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({trx['account']})."
            except Exception as e:
                print("⚠️ Eroare la inserarea tranzacției text-only:", str(e))
                return "⚠️ Sold actualizat, dar nu am reușit să salvez tranzacția."
        return f"❌ Eroare: {result.get('error', 'Nu s-a putut obține datele.')}"

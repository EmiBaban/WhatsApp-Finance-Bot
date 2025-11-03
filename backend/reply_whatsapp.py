from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import requests
from io import BytesIO
from PIL import Image
import requests
import re
from threading import Thread
from twilio.rest import Client as TwilioRestClient
from twilio.base.exceptions import TwilioRestException
from flask import Response
from twilio.twiml.messaging_response import MessagingResponse

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from doc_processing import extract_audio_text, process_image, answer_request, process_pdf
from services.pending import get_pending_action, clear_pending_action, present_candidates_message, present_candidates_message_with_all
from services.db_utils import compute_spent_sum

load_dotenv(".env")

OPENAI_KEY = os.getenv("OPENAI_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")

client = OpenAI(api_key=OPENAI_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# inițializează client Twilio REST odată (la top-level)
twilio_rest = TwilioRestClient(TWILIO_SID, TWILIO_AUTH)
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"  # înlocuiește cu numărul tău Twilio

def respond_xml(message):
    twiml = MessagingResponse()
    twiml.message(message)
    twiml_str = str(twiml)
    print("=== TwiML to Twilio ===")
    print(twiml_str)
    print("=======================")
    return Response(twiml_str, status=200, mimetype="application/xml")

def background_process_and_send(ext, sender, message, r, client, supabase_client):
    """
    Procesează fișierul (poza/pdf/audio) și trimite rezultatul folosind Twilio REST API.
    Rulare în background thread (nu blochează webhook-ul).
    """
    try:
        # Apelează funcțiile tale existente pentru procesare
        if ext == "pdf":
            # Procesează PDF-ul pentru a extrage informațiile din bon
            extracted_data = process_pdf(ext, sender, message, r, client, supabase_client)
            
            # Dacă avem și mesaj text (ex: "contul bcr"), îl folosim pentru a determina contul
            if message.strip():
                # Trimitem mesajul către GPT pentru a determina contul
                context_response = answer_request(message, extract_profile_from_whatsapp(sender), client, supabase_client)
                result = f"Context: {context_response}\nTranzacție: {extracted_data}"
            else:
                result = extracted_data
                
        elif ext in ("jpg", "png", "gif"):
            # Procesează imaginea pentru a extrage informațiile din bon
            extracted_data = process_image(ext, sender, message, r, client, supabase_client)
            
            # Dacă avem și mesaj text (ex: "contul bcr"), îl folosim pentru a determina contul
            if message.strip():
                # Trimitem mesajul către GPT pentru a determina contul
                context_response = answer_request(message, extract_profile_from_whatsapp(sender), client, supabase_client)
                result = f"Context: {context_response}\nTranzacție: {extracted_data}"
            else:
                result = extracted_data
                
        elif ext == "audio":
            audio_text = extract_audio_text(r, client)
            result = answer_request(audio_text, extract_profile_from_whatsapp(sender), client, supabase_client)
        else:
            result = "❌ Tip media necunoscut."

    except Exception as e:
        import traceback
        traceback.print_exc()
        result = f"❌ Eroare la procesare: {e}"

    # asigură-te că e string
    if not isinstance(result, str):
        try:
            result = str(result)
        except:
            result = "❌ Eroare la pregătirea rezultatului."

    # trimite mesajul outbound via Twilio REST (dacă nu depășim limita zilnică)
    try:
        twilio_rest.messages.create(
            body=result,
            from_=TWILIO_WHATSAPP_FROM,
            to=sender
        )
        print("Outbound message sent to", sender)
    except TwilioRestException as e:
        # 63038: sandbox daily messages limit
        if getattr(e, "code", None) == 63038 or "63038" in str(e):
            print("Twilio daily messages limit reached (63038). Skipping outbound send.")
        else:
            print("Failed to send outbound message:", e)
            import traceback; traceback.print_exc()


def extract_profile_from_whatsapp(from_value: str) -> str:
    # Twilio trimite 'whatsapp:+40...'
    return from_value

def get_account_balance(supabase: Client, iban: str, banca: str = "", compania: str = "") -> str:
    """
    Get account balance for a specific IBAN.

    Args:
        supabase: Supabase client instance
        iban: IBAN of the account
        banca: Bank name (for display purposes)
        compania: Company name (for display purposes)

    Returns:
        Formatted balance string or error message
    """
    try:
        result = supabase.table("Accounts").select("sum").eq("iban", iban).single().execute()
        if result.data:
            bal = result.data["sum"]
            account_name = f"{banca} - {compania}".strip(" -")
            if not account_name:
                account_name = iban
            return f"📊 Sold cont {account_name}: {bal:.2f} RON."
        else:
            return "❌ Eroare la obținerea soldului."
    except Exception as e:
        print(f"Error getting account balance: {e}")
        return "❌ Eroare la obținerea soldului."

def try_resolve_pending(supabase, profile_name, message_text):
    pending = get_pending_action(supabase, profile_name)
    # print("Pending action for", profile_name, ":", pending)
    if not pending:
        return None  # nimic de rezolvat

    payload = pending["payload"]
    candidates = payload["candidates"]
    op = pending["action_type"]
    search_term = payload.get("search_term")
    currency = payload.get("currency") or "RON"
    amount = payload.get("amount")
    print("Pending action:", op, "candidates:", candidates, "search_term:", search_term, "currency:", currency, "amount:", amount)

    text = (message_text or "").strip()

    # 1) dacă e număr/indecși multipli (permitem 0 pentru "toate conturile" la sum_spent)
    selected = None
    multi_selected = []
    # Acceptă: '1', '2', '1 2', '1,2', '1 si 2'
    indexes = re.findall(r'(\d+)', text)
    if indexes:
        idxs = [int(idx) for idx in indexes]
        if len(idxs) > 1 and op == "select":
            for idx in idxs:
                zero_based = idx - 1
                if 0 <= zero_based < len(candidates):
                    multi_selected.append(candidates[zero_based])
            if multi_selected:
                responses = []
                for candidate in multi_selected:
                    responses.append(get_account_balance(supabase, candidate["iban"], candidate.get("banca", ""), candidate.get("compania", "")))
                clear_pending_action(supabase, profile_name)
                return "\n".join(responses)
        elif len(idxs) == 1:
            idx = idxs[0] - 1
            if op == "sum_spent" and idxs[0] == 0:
                selected = "ALL"
            elif 0 <= idx < len(candidates):
                selected = candidates[idx]
                print("Selected by index:", selected)

        # 2) dacă e IBAN complet
        if not selected:
            iban_match = re.sub(r'\s+', '', text)
            if len(iban_match) >= 12 and iban_match[:2].isalpha():
                for c in candidates:
                    if re.sub(r'\s+','', c["iban"]) == iban_match:
                        selected = c
                        break

        # 3) dacă e IBAN complet și operațiunea este select, putem face query direct fără să alegem din candidates
        if not selected and op == "select":
            iban_match = re.sub(r'\s+', '', text)
            if len(iban_match) >= 12 and iban_match[:2].isalpha():
                # Facem query direct pentru IBAN-ul introdus
                balance_response = get_account_balance(supabase, iban_match)
                clear_pending_action(supabase, profile_name)
                return balance_response

    if not selected:
        # Daca textul corespunde partial unei companii sau banci, filtreaza candidatii
        text_lc = text.lower()
        filtered = [c for c in candidates if text_lc in c.get('compania', '').lower() or text_lc in c.get('banca', '').lower()]
        if filtered:
            return present_candidates_message(text, filtered)

        # re-afișăm opțiunile (cu ALL pentru sum_spent)
        if op == "sum_spent":
            return present_candidates_message_with_all(search_term, candidates)
        return present_candidates_message(search_term, candidates)

    # Executăm
    if op == "update":
        if not amount:
            clear_pending_action(supabase, profile_name)
            return "⚠️ Suma lipsește în acțiunea anterioară. Repetă comanda."
        # Asigură-te că amount este număr valid
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            clear_pending_action(supabase, profile_name)
            return "❌ Suma nu este validă."

        # Construiește tranzacția cu valori implicite pentru câmpuri opționale
        trx = {
            "amount": amount,
            "currency": currency or "RON",  # valoare implicită pentru currency
            "invoice_number": None,  # opțional, poate fi null
            "profile_name": profile_name or "unknown",  # valoare implicită dacă e null
            "account": selected["iban"],  # folosim IBAN-ul contului
            "description": payload.get("description")  # Include description from pending action
        }
        
        print("Inserting transaction:", trx)
        try:
            result = supabase.table("Transactions").insert(trx).execute()
            if not result.data:
                raise Exception("No data returned from insert")
        except Exception as e:
            print("Error inserting transaction:", str(e))
            clear_pending_action(supabase, profile_name)
            return f"❌ Eroare la salvarea tranzacției: {str(e)}"
        
        # Actualizăm soldul contului
        result = supabase.table("Accounts").select("sum").eq("iban", selected["iban"]).single().execute()
        if result.data:
            bal = result.data["sum"]
            clear_pending_action(supabase, profile_name)
            return f"✅ Am adăugat {float(amount):.2f} {currency} în contul {selected['banca']} - {selected['compania']}. Sold curent: {bal:.2f}."
        else:
            clear_pending_action(supabase, profile_name)
            return "❌ Eroare la actualizarea soldului."

    if op == "select":
        # Handle balance query (select operation)
        balance_response = get_account_balance(
            supabase,
            selected["iban"],
            selected.get("banca", ""),
            selected.get("compania", "")
        )
        clear_pending_action(supabase, profile_name)
        return balance_response

    if op == "sum_spent":
        period = payload.get("period")
        start_iso = payload.get("start_iso")
        end_iso = payload.get("end_iso")
        if selected == "ALL":
            total = compute_spent_sum(supabase, start_iso, end_iso, None)
            clear_pending_action(supabase, profile_name)
            return f"💸 Ai cheltuit {total:.2f} RON în total în perioada selectată (toate conturile)."
        else:
            total = compute_spent_sum(supabase, start_iso, end_iso, selected["iban"])
            clear_pending_action(supabase, profile_name)
            return f"💸 Ai cheltuit {total:.2f} RON în perioada selectată în {selected['banca']} - {selected['compania']} ({selected['iban']})."

    if op == "add_trx":
        amount = payload.get("amount")
        currency = payload.get("currency") or "RON"
        invoice_number = payload.get("invoice_number")
        # selected poate fi dict candidat sau IBAN (dacă userul a tastat IBAN complet)
        target_iban = selected if isinstance(selected, str) else selected["iban"]
        try:
            trx = {
                "amount": float(amount),
                "currency": currency,
                "invoice_number": invoice_number,
                "profile_name": profile_name or "unknown",
                "account": target_iban,
                "description": payload.get("description")  # Include description from pending action
            }
            supabase.table("Transactions").insert(trx).execute()
            
            # Obținem soldul contului pentru a-l afișa în confirmare
            try:
                balance_result = supabase.table("Accounts").select("sum").eq("iban", target_iban).single().execute()
                if balance_result.data:
                    current_balance = balance_result.data["sum"]
                    clear_pending_action(supabase, profile_name)
                    return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({target_iban}). Sold curent: {current_balance:.2f} RON."
                else:
                    clear_pending_action(supabase, profile_name)
                    return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({target_iban})."
            except Exception as balance_error:
                print(f"Error getting balance: {balance_error}")
                clear_pending_action(supabase, profile_name)
                return f"✅ Tranzacție salvată: {trx['amount']:.2f} {trx['currency']} ({target_iban})."
        except Exception as e:
            clear_pending_action(supabase, profile_name)
            return f"❌ Eroare la salvarea tranzacției: {str(e)}"

    clear_pending_action(supabase, profile_name)
    return "❌ Operațiune necunoscută."

def undo_last_transaction(supabase, profile_name):
    # 1. Găsește ultima tranzacție (presupunem doar tranzacții pozitive, nu credit)
    trx = supabase.table("Transactions")\
        .select("*")\
        .eq("profile_name", profile_name)\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    if not trx.data:
        return "❌ Nu am găsit nicio tranzacție de anulat."
    last = trx.data[0]
    iban = last["account"]
    amount = float(last["amount"])
    # 2. Șterge tranzacția
    supabase.table("Transactions").delete().eq("id", last["id"]).execute()
    # 3. Aplică operația inversă în Accounts
    account = supabase.table("Accounts").select("sum").eq("iban", iban).single().execute()
    if not account.data:
        return "❌ Contul nu există, dar tranzacția a fost ștearsă."

    return f"✅ Tranzacția de {amount:.2f} RON a fost anulată, soldul contului a fost actualizat."

def is_new_intent(msg):
    keywords = [
        "plătesc", "am plătit", "plata", "sold", "cât am", "extras", "raport", "transfer", "cheltuit", "vreau să transfer", "am primit"
    ]
    return any(kw in msg.lower() for kw in keywords)


@app.route("/reply_whatsapp", methods=['POST'])
def reply_whatsapp():
    try:
        # extrage mesajul
        message = request.values.get('Body', '') or ''
        # extrage sender-ul
        sender = request.values.get('From', '')
        num_media = int(request.values.get('NumMedia', 0))
        profile_name = extract_profile_from_whatsapp(sender)
        # Detectează undo
        if message.strip() and any(kw in message.lower() for kw in ["undo", "anuleaza", "anulează", "sterge ultima", "șterge ultima", "retrag ultima tranzactie", "retrag ultima tranzacție"]):
            resp = undo_last_transaction(supabase, profile_name)
            return respond_xml(resp)
        if message:
            # Daca mesajul este o intentie noua, stergem pending-ul vechi
            if is_new_intent(message):
                clear_pending_action(supabase, profile_name)
            pending_reply = try_resolve_pending(supabase, profile_name, message)
            print("Pending reply:", pending_reply)
            if pending_reply is not None:
                return respond_xml(pending_reply)
            
        # extrage primul fisier media trimis
        media_url = request.values.get('MediaUrl0') if num_media > 0 else None
        media_type = request.values.get('MediaContentType0', '') or ''

        if media_url:
            r = requests.get(media_url, auth=(TWILIO_SID, TWILIO_AUTH), timeout=20)
            if r.status_code != 200:
                return respond_xml(f"❌ Eroare la descărcare media: {r.status_code}")

            # detectare ext
            content_type = (media_type or r.headers.get("Content-Type", "")).lower()
            ext = None
            if "pdf" in content_type: ext = "pdf"
            elif "jpeg" in content_type or "jpg" in content_type: ext = "jpg"
            elif "png" in content_type: ext = "png"
            elif "gif" in content_type: ext = "gif"
            elif "ogg" in content_type or "wav" in content_type or "mpeg" in content_type or "mp3" in content_type:
                ext = "audio"

            # pornește background thread și ACK imediat
            Thread(
                target=background_process_and_send,
                args=(ext, sender, message, r, client, supabase),
                daemon=True
            ).start()

            return respond_xml("✅ Am primit fișierul și îl procesez. Vei primi rezultatul în curând.")
        
        # fallback text-only (rapid)
        if message.strip():
            resp = answer_request(message, profile_name, client, supabase)
            return respond_xml(resp if isinstance(resp, str) else str(resp))

        return respond_xml("⚠️ Mesajul nu conține text sau media recunoscută.")
    except Exception as e:
        import traceback; traceback.print_exc()
        return respond_xml(f"❌ A apărut o eroare internă: {e}")


if __name__ == "__main__":
    # port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=3000)
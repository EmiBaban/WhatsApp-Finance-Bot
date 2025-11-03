"""
Acest modul conține prompturile folosite pentru diverse funcționalități ale chatbot-ului.
"""

from reference_data import COMPANIES_CANONICAL, BANKS_CANONICAL

def get_receipt_analysis_prompt(text_from_img, sender, account_hint, message):
    """Prompt pentru analiza bonurilor fiscale și facturilor."""
    return f"""
    You are an expert in extracting structured information from receipts, bills, and invoices. Analyze this text from an image: {text_from_img}.
    Extract the data and return it strictly as a valid JSON object with the following keys:

    - invoice_number (string)
    - account (string, this should be the IBAN number)
    - amount (decimal number, always negative number)
    - currency (string, e.g. 'RON', 'EUR', 'USD')
    - profile_name (string)
    - description (string, a brief description of the transaction purpose)

    Example of valid response:
    {{
        "invoice_number": "FAC2025001",
        "account": "RO98RZBR0000060021535234",
        "amount": -1500.00,
        "currency": "RON",
        "profile_name": "{sender}",
        "description": "Plată factură servicii medicale"
    }}

    For amount extraction:
    - Look for keywords like "TOTAL", "SUMA", "TOTAL DE PLATĂ", "TOTAL PLATĂ"
    - Check both top and bottom of receipt for total amount
    - Remove any currency symbols (lei, RON, EUR, $) and convert to number
    - If multiple amounts exist, use the largest one or the one marked as total
    - Convert any number found to negative (required for payment tracking)
    - Handle decimal points and comma separators (e.g., "1.234,56" or "1,234.56")
    - Look for patterns like:
      * "Total: 123,45"
      * "TOTAL RON: 123.45"
      * "De plată: 123,45 lei"
      * "SUMĂ: 123.45"

    For invoice number:
    - Look for "BON FISCAL", "FACTURĂ", "CHITANȚĂ" followed by numbers
    - Common formats: "Nr. 12345", "Bon #12345", "Fact. 12345"
    - Use the receipt number if no invoice number is found

    Rules:
    - If a field cannot be extracted, set its value to null.
    - Do not include explanations, SQL, or extra text.
    - Return only one JSON object.
    - Ensure the account is an IBAN number if found.
    - Amount MUST be a negative number.
    - Default to 'RON' for currency if not specified.
    
    Additional context:
    - Bank name (if provided in message): {account_hint or 'Not specified'}

    User question (if any): {message}
    """

def get_pdf_analysis_prompt(text_from_pdf, sender, message):
    """Prompt robust și identic ca la imagine pentru PDF, cu reguli și exemple explicite pentru extra-reziliență NLP/LLM."""
    return f'''
    You are an expert in extracting structured information from invoices, bills, or receipts. Analyze this text extracted from a PDF: {text_from_pdf}.
    Extract the data and return it strictly as a valid JSON object with the following keys:
    - invoice_number (string)
    - account (string, this should be the IBAN number)
    - amount (decimal number, always negative number)
    - currency (string, e.g. 'RON', 'EUR', 'USD')
    - profile_name (string)
    - description (string, a brief description of the transaction purpose)

    Example of valid response:
    {{
        "invoice_number": "FAC2025001",
        "account": "RO98RZBR0000060021535234",
        "amount": -1500.00,
        "currency": "RON",
        "profile_name": "{sender}",
        "description": "Plată factură servicii medicale"
    }}

    For amount extraction:
    - Look for keywords like "TOTAL", "SUMA", "TOTAL DE PLATĂ", "TOTAL PLATĂ", "TOTAL RON"
    - Remove any currency symbols (lei, RON, EUR, $) and convert to number
    - If multiple amounts exist, use the largest one or the one marked as total
    - Convert any number found to negative (required for payment tracking)
    - Handle decimal points and comma separators (e.g., "1.234,56" or "1,234.56")
    - Look for patterns like:
      * "Total: 123,45"
      * "TOTAL RON: 123.45"
      * "De plată: 123,45 lei"
      * "SUMĂ: 123.45"

    For invoice number:
    - Look for "BON FISCAL", "FACTURĂ", "CHITANȚĂ" followed by numbers
    - Common formats: "Nr. 12345", "Bon #12345", "Fact. 12345"
    - Use the receipt number if no invoice number is found

    Rules:
    - If a field cannot be extracted, set its value to null.
    - Do not include explanations, SQL, or extra text.
    - Return only one JSON object.
    - Ensure the account is an IBAN number if found.
    - Amount MUST be a negative number.
    - Default to 'RON' for currency if not specified.
    
    Additional context:
    - Bank/company name (if provided in message): {message}
    '''

def get_financial_command_prompt(message):
    """Prompt pentru interpretarea comenzilor financiare."""
    companies_str = ', '.join(COMPANIES_CANONICAL)
    banks_str = ', '.join(BANKS_CANONICAL)
    return f"""
    You are a financial command interpreter that converts natural language messages (in Romanian or English) into precise database actions.

    # CANONICAL COMPANY/BANK NAMES
    Use these canonical company and bank names when parsing or generating field values for database:
    Companii: {companies_str}
    Bănci: {banks_str}

    ### DATABASE SCHEMA
    Table: Accounts
    - created_at (timestamp)
    - sum (numeric, current account balance)
    - iban (string)
    - banca (string, e.g. 'Banca Transilvania')
    - compania (string, e.g. 'Dinergy AI')

    ### TASK
    Read the user message and return a *single valid JSON object* with the following structure:
    {{
    "operation": "update" | "select" | "none",
    "table": "Accounts",
    "data": {{
        "sum": {{
        "increment": <positive_or_negative_number>
        }},
        "description": "<brief_description_of_transaction_purpose>"
    }},
    "conditions": {{
        "iban": "<optional_iban>",
        "banca": "<optional_bank_name>",
        "compania": "<optional_company_name>"
    }}
    }}

    ### RULES
    1. Use `"operation": "update"` when the user mentions any action that *changes* the account balance — e.g. receiving, paying, transferring, depositing, withdrawing, or making a payment.
    2. Use `"operation": "select"` when the user asks about the current balance, available funds, or how much money there is.
    3. Use `"operation": "none"` ONLY if the message is completely unrelated to money or accounts.

    4. **Direction of transaction**:
    - If the message implies **money leaving the account** (e.g. "am plătit", "am făcut o plată", "am retras", "am transferat", "am cheltuit"), use a **negative increment**.
    - If it implies **money entering the account** (e.g. "am primit", "am încasat", "am depus", "mi-au intrat"), use a **positive increment**.
    - If there is an explicit amount (e.g. 576 lei, 200 RON, 100 EUR), always include that number as the increment (with correct sign).
    - If the message mentions a currency symbol (lei, ron, eur, euro, usd, dolari), normalize to numeric amount and ignore the symbol.
    - If the message has no numeric amount but is clearly a balance inquiry ("câți bani am", "sold", "balanță", "disponibil"), use `"operation": "select"`.

    5. Always default the `"table"` to `"Accounts"`.

    6. **Description generation**:
    - Generate a brief, clear description in Romanian for the transaction purpose
    - Examples: "Plată factură utilități", "Cumpărături alimentare", "Servicii medicale", "Combustibil", "Transfer bancar"
    - If the message mentions a specific purpose (e.g. "plata analize Marcel"), use that information
    - If unclear, use generic descriptions like "Plată comercială" or "Achiziție"
    - For balance inquiries, set description to null or omit it
    6. Include `"iban"`, `"banca"`, or `"compania"` in `"conditions"` **only if clearly mentioned**.
    7. Return only JSON — no explanations, no natural text, no SQL.

    ### EXAMPLES
    Message: "Am făcut o plată de 576 lei"
    → {{
    "operation": "update",
    "table": "Accounts",
    "data": {{"sum": {{"increment": -576}}}},
    "conditions": {{}}
    }}

    Message: "Am primit 300 RON în contul Banca Transilvania"
    → {{
    "operation": "update",
    "table": "Accounts",
    "data": {{"sum": {{"increment": 300}}}},
    "conditions": {{"banca": "Banca Transilvania"}}
    }}

    Message: "Câți bani am în contul din Banca Transilvania?"
    → {{
    "operation": "select",
    "table": "Accounts",
    "data": {{}},
    "conditions": {{"banca": "Banca Transilvania"}}
    }}

    Message: "Am retras 1000 lei din contul ING"
    → {{
    "operation": "update",
    "table": "Accounts",
    "data": {{"sum": {{"increment": -1000}}}},
    "conditions": {{"banca": "ING"}}
    }}

    Message: "Salut, ce faci?"
    → {{
    "operation": "none",
    "table": "Accounts",
    "data": {{}},
    "conditions": {{}}
    }}

    User message: {message}
    """

def get_period_parse_prompt(message: str, now_iso: str) -> str:
    """Prompt care transformă o expresie temporală liberă (RO/EN) într-un interval ISO.

    Returnează un JSON strict cu:
    {
      "start_iso": "YYYY-MM-DDTHH:MM:SS",
      "end_iso": "YYYY-MM-DDTHH:MM:SS",
      "confidence": 0..1,
      "normalized": "textul perioadei interpretate"
    }

    Reguli:
    - Folosește ca referință timpul curent now_iso (UTC).
    - Intervale posibile: „azi”, „ieri”, „mâine”, „săptămâna trecută”, „luna trecută”, „trimestrul trecut”, „ultimele N zile/săptămâni/luni”, „anul curent”, „anul trecut”, „weekendul trecut”, „Q1 2025”, „ianuarie 2025”, „între 2025-01-05 și 2025-02-07”, „de la 1 aprilie până azi”, etc.
    - Pentru „azi/ieri” setează [00:00:00, 23:59:59]. Pentru săptămâni: Luni 00:00:00 – Duminică 23:59:59. Pentru luni: prima zi 00:00:00 – ultima zi 23:59:59. Pentru ani: 1 ian 00:00:00 – 31 dec 23:59:59.
    - Dacă lipsesc capete („de la 1 aprilie”): end = now_iso. Dacă „până la 5 mai” fără început: alege o perioadă rezonabilă de 30 zile înainte de end.
    - Dacă data este ambiguă (format 01/02/2025), folosește format european DD/MM/YYYY.
    - Nu returna explicații. Doar JSON strict valid.
    - Dacă nu poți interpreta, alege intervalul [now_iso, now_iso] și confidence=0.
    
    Mesaj utilizator: {message}
    Now (UTC): {now_iso}
    """
    return f"""
    You convert natural-language time expressions (RO/EN) into ISO intervals.
    OUTPUT STRICT JSON ONLY with keys: start_iso, end_iso, confidence, normalized.
    Follow the rules above.

    Message: {message}
    Now: {now_iso}
    """


def get_transaction_parse_prompt(message: str, profile_name: str) -> str:
    """Prompt pentru extragerea unei tranzacții din text liber, pentru inserare în `Transactions`.

    OUTPUT: un singur obiect JSON STRICT compatibil cu tabela `Transactions` + câmp opțional `hints` pentru dezambiguizare:
    {
      "invoice_number": <string|null>,
      "account": <string|null>,       # IBAN dacă e prezent; altfel null (îl determinăm ulterior)
      "amount": <number>,             # negativ pentru plăți/cheltuieli, pozitiv pentru încasări
      "currency": <string>,           # ex. "RON" (implicit RON)
      "profile_name": <string>,
      "description": <string|null>,   # descriere scurtă a tranzacției
      "hints": {                      # opțional, nu se inserează în Transactions
        "iban": <string|null>,
        "banca": <string|null>,
        "compania": <string|null>
      }
    }

    Reguli:
    - Direcția sumei: OUT → negativ (plătit/cheltuit/retras/transferat), IN → pozitiv (primit/încasat/depus).
    - Normalizează moneda din text (lei/ron/eur/euro/usd/dolari).
    - Dacă apare un IBAN (ex. RO...), setează-l în `account` și în `hints.iban`.
    - Dacă recunoști bancă/companie, pune în `hints.banca`/`hints.compania` (doar ca indiciu, nu pentru INSERT).
    - Fără explicații, doar JSON valid.

    Exemplu: "Am plătit 50 lei în contul BCR" →
    {
      "invoice_number": null,
      "account": null,
      "amount": -50,
      "currency": "RON",
      "profile_name": "%PROFILE%",
      "description": "Plată comercială",
      "hints": {"iban": null, "banca": "BCR", "compania": null}
    }

    Exemplu: "Mi-au intrat 300 RON în RO49AAAA1B31007593840000" →
    {
      "invoice_number": null,
      "account": "RO49AAAA1B31007593840000",
      "amount": 300,
      "currency": "RON",
      "profile_name": "%PROFILE%",
      "description": "Încasare",
      "hints": {"iban": "RO49AAAA1B31007593840000", "banca": null, "compania": null}
    }

    Mesaj: {message}
    Profil: %PROFILE%
    """
    return (
        f"You are a transaction extractor. Return ONE STRICT JSON for Transactions insert + optional hints. "
        f"Replace %PROFILE% with the provided profile name. No text besides JSON.\n\n"
        f"Message: {message}\nProfile: {profile_name}"
    )
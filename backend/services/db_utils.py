import re
import json
from datetime import datetime, timedelta, timezone


def get_normalized_mapping(supabase_client):
    """Return dicts mapping normalized keys to original names for companies and banks."""
    result = supabase_client.table("Accounts").select("compania,banca").execute()
    company_mapping = {}
    bank_mapping = {}

    for row in result.data or []:
        if row.get("compania"):
            original = row["compania"]
            normalized = original.lower().replace(" ", "", 1).replace(" ", "") if "  " in original else original.lower().replace(" ", "")
            normalized = original.lower().replace(" ", "")
            company_mapping[normalized] = original

        if row.get("banca"):
            original = row["banca"]
            normalized = original.lower().replace(" ", "")
            bank_mapping[normalized] = original

    return company_mapping, bank_mapping


def mask_iban(iban: str) -> str:
    s = re.sub(r"\s+", "", iban or "")
    if len(s) <= 8:
        return s
    return f"{s[:6]}…{s[-4:]}"


def get_last_week_range():
    today = datetime.now(timezone.utc).date()
    weekday = today.weekday()  # Monday=0
    start_this_week = datetime.combine(today - timedelta(days=weekday), datetime.min.time()).replace(tzinfo=timezone.utc)
    start_last_week = start_this_week - timedelta(days=7)
    end_last_week = start_this_week - timedelta(seconds=1)
    return start_last_week.isoformat(), end_last_week.isoformat()


def compute_spent_sum(supabase_client, start_iso: str, end_iso: str, iban: str | None = None):
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


def execute_db_action(supabase_client, json_text):
    action = json.loads(json_text)
    operation = action.get("operation")
    table = action.get("table")
    data = action.get("data")
    conditions = action.get("conditions")

    try:
        if operation == "update":
            if not data or not conditions:
                return {"error": "Missing data or conditions for update."}
            updates = {}
            for k, v in data.items():
                if isinstance(v, dict) and "increment" in v:
                    account = conditions.get("iban")
                    current_resp = supabase_client.table(table).select(k).eq("iban", account).execute()
                    current_val = current_resp.data[0][k] if current_resp.data else 0
                    updates[k] = current_val + v["increment"]
                else:
                    updates[k] = v

            response = supabase_client.table(table).update(updates).eq(
                list(conditions.keys())[0],
                list(conditions.values())[0]
            ).execute()
            return {"status": "success", "response": response}

        elif operation == "select":
            account = conditions.get("iban") if conditions else None
            if not account:
                return {"error": "Missing conditions for select."}
            resp = supabase_client.table(table).select("*").eq("iban", account).execute()
            return {"status": "success", "response": resp}

        else:
            return {"error": f"Operation '{operation}' not supported."}

    except Exception as e:
        return {"error": str(e)}



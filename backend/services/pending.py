from .db_utils import mask_iban


def save_pending_action(supabase, profile_name, action_type, payload: dict):
    supabase.table("Pending_Actions").delete().eq("profile_name", profile_name).execute()
    return supabase.table("Pending_Actions").insert({
        "profile_name": profile_name,
        "action_type": action_type,
        "payload": payload
    }).execute()


def get_pending_action(supabase, profile_name):
    resp = supabase.table("Pending_Actions") \
        .select("*").eq("profile_name", profile_name) \
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
        description = f"{banca} {compania}".strip() or "cont"
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
        description = f"{banca} {compania}".strip() or "cont"
        lines.append(f"{zws}{i}) {description} — {mask_iban(iban)}")
    lines.append("Răspunde cu *0* pentru toate conturile, *1* sau *2* … ori trimite IBAN-ul complet.")
    return "\n".join(lines)



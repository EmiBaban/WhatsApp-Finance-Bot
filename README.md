# WhatsAppBot - Asistent Financiar pe WhatsApp

WhatsAppBot este un asistent dedicat pentru gestionarea rapidă a conturilor financiare și înregistrarea tranzacțiilor direct din conversație pe WhatsApp. Proiectul permite utilizatorului să efectueze acțiuni specifice asupra conturilor bancare, să trimită documente relevante și să primească răspunsuri clare, automatizate, fără a fi nevoie de interacțiune manuală asupra datelor financiare.

---

## Scopul proiectului

- Oferirea unei interfețe simple pe WhatsApp pentru operarea conturilor financiare.
- Înregistrarea automată a tranzacțiilor (adăugare/retragere sume, plăți).
- Trimiterea și interpretarea automată a facturilor (imagini, PDF-uri).
- Procesarea mesajelor audio pentru extragerea datelor financiare.

---

## Cum funcționează botul

- **Mesaje acceptate:** Botul nu răspunde la conversații normale, ci doar la acțiuni asupra conturilor bancare din baza de date.
- **Adăugare bani:** Poți adăuga sume în orice cont bancar printr-o cerere directă în chat.
- **Retragere bani / Plăți:** Poți scădea bani din cont, de exemplu: `am făcut o plată de 100 de lei`. Plata trebuie să fie menționată ca fiind efectuată de către utilizator pentru ca botul să știe să scadă suma din cont.
- **Conturi bancare:** Nu este necesar să specifici IBAN-ul în mesaj. Dacă nu dai niciun detaliu despre cont, botul va returna o listă numerotată cu toate conturile disponibile. Poți selecta contul dorit trimițând numărul său în chat. Poți selecta mai multe conturi, chiar toate, pentru operare simultană.
- **Documente și fișiere:** Poți trimite imagini sau PDF-uri, dar doar dacă acestea conțin toate informațiile despre cont (facturi). Nu se acceptă bonuri fiscale, imagini + text separat sau fișiere incomplete.
- **Sold și tranzacții:** Botul poate răspunde la întrebări despre soldul curent în cont sau despre cheltuieli într-o anumită perioadă (de exemplu: „azi”, „ieri”, „data exactă”, „săptămâna trecută” etc.).
- **Mesaje audio:** Poți trimite mesaje audio pentru a fi interpretate automat și pentru a efectua operațiuni asupra conturilor.

---

## Funcționalități principale

- **Operare rapidă a conturilor bancare** (adăugare/retragere sume, plăți efectuate).
- **Selectarea contului bancar** prin listă automată sau detalii din mesaj.
- **Interpretarea automată a facturilor/imagini/PDF-uri** pentru înregistrarea plăților.
- **Procesarea mesajelor audio** pentru comenzi financiare.
- **Răspunsuri clare** privind soldul și istoricul tranzacțiilor pe perioade selectate.

---

## Instrucțiuni de utilizare

1. **Activează botul** și asigură-te că are acces la contul tău WhatsApp și la baza de date cu conturi bancare.
2. **Trimite o acțiune financiară** (ex: „adaugă 200 lei în contul personal” sau „am făcut o plată de 100 lei”).
3. **Dacă nu specifici contul**, botul va returna automat o listă cu toate conturile disponibile. Selectează contul dorit trimițând numărul său.
4. **Poți trimite facturi sub formă de imagine sau PDF**; botul va interpreta automat informațiile dacă documentul este complet.
5. **Cere soldul sau istoricul tranzacțiilor**: „Care e soldul?”, „Cât am cheltuit luna trecută?” etc.
6. **Trimite mesaje audio** cu comenzi sau întrebări legate de conturi și tranzacții.

---

## Observații

- Botul funcționează exclusiv pentru operațiuni financiare și nu acceptă conversații generale.
- Pentru interpretarea corectă, documentele trebuie să fie complete și să conțină toate datele relevante despre cont și tranzacție.
- Sistemul este extensibil și poate fi adaptat în funcție de nevoile utilizatorului.

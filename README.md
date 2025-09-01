# ITIL 4 Foundation trainer

Desktop-quiz/app om ITIL 4 Foundation te oefenen.  
De vraagbestanden (JSON) staan in `assets/itil_vragen/`.

## Snel starten (Windows)

- Start de app met: **`ITIL 4 Foundation.exe`**  
- Extra leermateriaal staat in **`assets/extra/`** (presentaties, samenvatting, exam objectives).

## Zelf de broncode aanpassen?
Als je zelf dingen hebt aangepast in de broncode dan moet je eerst dubbel klikken op build_itil.bat
Deze bat file bouwt de app opnieuw op zodat de veranderingen mee opgenomen worden de volgende keer
dat je op itil4_foundation.exe klikt.
Opnieuw opbouwen van de app kan een paar minuten duren.

## Uit broncode draaien

Vereist: Python 3.9+ en Pillow.
```bash
python --version
pip install pillow
python itil.py

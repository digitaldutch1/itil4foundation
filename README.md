# ITIL 4 Foundation trainer

Desktop-quiz/app om ITIL 4 Foundation te oefenen.  
De vraagbestanden (JSON) staan in `assets/itil_vragen/`.

## Snel starten (Windows)

1. **Download** de repo (via **Code → Download ZIP**) en pak uit.
2. **Start de app** met: `ITIL 4 Foundation.exe`  
   > Let op: Windows SmartScreen kan vragen om bevestiging. Klik **Meer info** → **Toch uitvoeren**.
3. Extra leermateriaal staat in `assets/extra/` (presentaties, samenvatting, exam objectives).

## Zelf de broncode aanpassen?

Als je de broncode aanpast, bouw dan de app opnieuw met **`build_itil.bat`**.  
Deze batch bouwt de .exe opnieuw met PyInstaller. Dit kan een paar minuten duren.

## Uit broncode draaien

Vereist: **Python 3.9+** en **Pillow**.

```bash
python --version
pip install pillow
python itil.py


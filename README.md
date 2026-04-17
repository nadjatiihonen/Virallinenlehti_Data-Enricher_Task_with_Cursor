# Virallinen-lehti Data Enricher

## 📋 Yleiskatsaus
Tämä projekti on automatisoitu ratkaisu historiallisen konkurssi- ja yrityssaneeraustiedon keräämiseen Virallisesta lehdestä (virallinenlehti.fi). Koska tieto on saatavilla vain PDF-muodossa, projekti hyödyntää modernia tekoälypohjaista tekstinlouhintaa datan rikastamiseksi ja rakenteistamiseksi.

## 🚀 Teknologiat
* **Python** (Core logic)
* **Cursor AI** (Development & AI-pair programming)
* **PyMuPDF** (High-performance PDF parsing)
* **Instructor & OpenAI GPT-4o-mini** (Structured data extraction)
* **Pydantic** (Data validation)
* **Pandas** (Excel staging & data manipulation)

## 🛠️ Arkkitehtuuri
1. **Scraping:** PDF-tiedostojen automaattinen haku arkistosta.
2. **Filtering:** Relevanttien sivujen tunnistus avainsana-analyysilla (kustannustehokkuus).
3. **Extraction:** Epärakenteisen tekstin muuntaminen JSON-muotoon LLM:n avulla.
4. **Validation:** Y-tunnusten ja päivämäärien automaattinen tarkistus.
5. **Staging:** Datan vienti Excel-muotoon laadunvarmistusta varten.
6. **Integration:** Validoidun datan lataus kohdejärjestelmään API-rajapinnan kautta.

## 📈 Tavoite
Rikastaa yritystietokantaa tarkalla historiallisella tiedolla, joka on aiemmin ollut vaikeasti saavutettavissa manuaalisen työn vuoksi.

## 🧪 Kehitysymparisto ja testaus
Asenna ensin kehitystyokalut:

```bash
python3 -m pip install -r requirements-dev.txt
```

Aja testit:

```bash
python3 -m pytest
```

Aja linttaus:

```bash
python3 -m ruff check .
```

Aja tyyppitarkistus:

```bash
python3 -m mypy .
```

## ✅ Mitä korjattiin testauksen yhteydessä
- `extractor.py`: tapahtuma-enum muutettiin `StrEnum`-muotoon, jotta linttaus ja tyyppitarkistus ovat yhdenmukaiset.
- `src/__init__.py` lisättiin, jotta moduulirakenne toimii selkeasti mypy-tarkistuksessa.
- `pyproject.toml`: mypy-asetuksia tarkennettiin (mm. package base -ratkaisu ja import-overrides), jotta tarkistus toimii vakaasti.
- `parser.py`: avainsanahakua parannettiin suomen taivutusmuotojen varalta (`-minen` runko), jotta relevantit osumat tunnistuvat paremmin.
- `uploader.py`: tyypitykset viimeisteltiin (`TypedDict`) ja raporttirakenne tehtiin eksplisiittiseksi.

## 🚦 Suositus tästä eteenpäin
Käytä seuraavaa tarkistusporttia ennen jokaista mergea tai julkaisua:

```bash
python3 -m ruff check .
python3 -m mypy .
python3 -m pytest
docker compose up --build --abort-on-container-exit
```

Jos kaikki nelja vaihetta menevat lapi, ETL-putki on validoitu seka paikallisesti etta konttiymparistossa.

## 🔐 Ympäristömuuttujat
- `OPENAI_API_KEY`: pakollinen `extractor.py`-vaiheelle.
- `YRITYSDATA_API_URL`: valinnainen; jos puuttuu, `uploader.py` tallentaa CSV-fallbackin.
- `YRITYSDATA_API_TOKEN`: pakollinen vain jos `YRITYSDATA_API_URL` on asetettu.
- `EXTRACTOR_DRY_RUN`: aseta arvoon `1`, jos haluat skipata LLM-kutsut smoke-ajossa.

## 📘 Operointirunbook
- Aja koko putki Dockerilla: `docker compose up --build --abort-on-container-exit`
- Tarkista lopputulos tiedostoista: `data/final/`
- Jos API ei ole käytössä, käytä `data/final/konkurssitiedot_staging.csv` jatkojalostukseen.
- Jos upload epäonnistuu, tarkista `data/final/upload_report.json`.
- Upload-raportissa on nyt myös `success_count` ja `failed_count` nopeaa hälytysseurantaa varten.
- CI-workflow ajetaan pusheissa, PR:issä, manuaalisesti ja aikataulutettuna kerran päivässä.
- CI tallentaa `data/final/`-kansion artifactina jokaisessa ajossa (`etl-final-output`) helpottamaan debugointia.

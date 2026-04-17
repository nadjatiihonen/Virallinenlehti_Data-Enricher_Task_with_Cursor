# Tekninen toteutussuunnitelma: Virallinen lehti -PDF-datan rikastus

## 1) Ongelman kuvaus ja tavoite

Tavoitteena on automatisoida konkurssi- ja yrityssaneerausilmoitusten poiminta Virallisen lehden PDF-julkaisuista, muuntaa tiedot rakenteiseen muotoon ja tuottaa laadukas datasetti jatkokäyttöön (API-lataus tai CSV/Excel-staging).

Ratkaisun tulee:
- hakea PDF:t automaattisesti arkistosta
- tunnistaa vain relevantit sivut kustannustehokkaasti
- poimia keskeiset kentät epästrukturoidusta tekstistä
- validoida data (esim. Y-tunnus, päivämäärä)
- viedä data tuotantokelpoiseen formaattiin
- toimia toistettavasti (Docker + CI)

## 2) Arkkitehtuuri ja teknologiavalinnat

### Kokonaisarkkitehtuuri (ETL + validointi)

1. **Extract**
   - PDF-lataus arkistosta URL-mallilla.
2. **Filter**
   - Sivukohtainen avainsanasuodatus, jotta LLM-kutsuja vähennetään.
3. **Transform**
   - LLM-pohjainen rakenteinen poiminta määriteltyyn skeemaan.
4. **Validate**
   - Pydantic-mallivalidointi (enumit, regex, päivämäärät).
5. **Load**
   - Excel/CSV-staging sekä vaihtoehtoisesti API-lähetys.

### Teknologiat ja perustelut

- **Python 3.11**
  - Kypsä ekosysteemi datankäsittelyyn, automaatioon ja integraatioihin.
- **PyMuPDF (fitz)**
  - Nopea ja luotettava PDF-tekstin luku sivuittain.
- **OpenAI GPT-4o-mini + Instructor**
  - Kustannustehokas LLM rakenteiseen poimintaan; Instructor vähentää parserivirheitä.
- **Pydantic**
  - Tiukka skeema ja validointi, virheiden varhainen tunnistus.
- **Pandas + OpenPyXL**
  - Helppo ja standardi tapa staging-vientiin (Excel/CSV).
- **Requests**
  - Yksinkertainen HTTP-asiakas latauksiin ja API-kutsuihin.
- **Docker + docker-compose**
  - Toistettava ajo missä tahansa ympäristössä.
- **GitHub Actions**
  - Automaattinen laadunvarmistus (lint, mypy, testit, Docker smoke-run).

## 3) Datan käsittely: miten PDF-data poimitaan

### 3.1 Lataus
- Rakennetaan URL muodossa:
  `https://www.virallinenlehti.fi/fi/journal/pdf/{vuosi}{numero}.pdf`
- Tallennus `data/raw`-kansioon.
- Retry + timeout + virheenkäsittely (404, verkko-ongelmat).

### 3.2 Sivutason suodatus (kustannustehokkuus)
- Luetaan PDF sivu kerrallaan.
- Tunnistetaan "kuumat sivut" avainsanoilla, esim.:
  - konkurssi
  - yrityssaneeraus
  - alkaminen / lakkaaminen (taivutusmuodot huomioiden)
- Tallennetaan vain relevantti sivuteksti + metadata (`lahdetiedosto`, `sivunumero`) JSON:iin.

### 3.3 LLM-pohjainen rakenteistus
- Jokainen relevantti sivu lähetetään mallille rajatulla promptilla.
- Palautus suoraan Pydantic-skeemaan (`YritysTapahtuma`), kentät:
  - `tapahtuma_tyyppi` (enum)
  - `y_tunnus` (regex)
  - `yrityksen_nimi`
  - `tapahtuman_pvm`
  - `lahdetiedosto`
  - `sivunumero`
- Validointivirheet lokitetaan ja virheelliset rivit hylätään.

### 3.4 Staging ja lataus
- Tallennetaan validi data:
  - JSON (`data/final/yritystapahtumat.json`)
  - Excel (`konkurssitiedot_staging.xlsx`)
  - CSV fallback, jos API-endpoint puuttuu.
- API-lähetys (jos käytössä):
  - Bearer-token
  - rivikohtainen raportointi onnistuneista/epäonnistuneista
  - retry transient-virheille.

## 4) Laatu, tuotantokelpoisuus ja riskienhallinta

### Laadunvarmistus
- **Yksikkötestit + mockit** (LLM/API ei vaadi oikeita kutsuja testissä)
- **Ruff** (lint), **mypy** (tyypit), **pytest-cov** (kattavuus)
- **Docker smoke run** CI:ssä
- Artifactit talteen CI-ajosta (`data/final`) debugointiin.

### Tietoturva
- API-avaimet vain `.env`-tiedostossa.
- `.env` ja generoitu data (`data/raw|processed|final`) gitignoreen.
- Ei salaisuuksia koodissa tai dokumentaatiossa.

### Keskeiset riskit ja mitigointi
- **PDF-rakenne vaihtelee** -> avainsanakerros + skeemavalidointi + lokit.
- **LLM-hallusinaatiot** -> tiukka prompt, vain eksplisiittiset faktat, Pydantic-hylkäys.
- **API/verkko-ongelmat** -> retry/backoff + fallback CSV.
- **Duplikaatit uusinta-ajossa** -> suositus: lisää idempotenssiavain (esim. hash kentistä) tuotantoversioon.

## 5) Aika-arvio (tuotantokuntoon)

Jos toteuttaisin projektin alusta tuotantokuntoon:

- Arkkitehtuurisuunnittelu + spesifikaatio: **0.5-1 päivä**
- ETL-perusrunko (download, parse, extract, export, upload): **2-3 päivää**
- Validointi, virheenkäsittely, retryt, fallbackit: **1-1.5 päivää**
- Testit (unit + mock + smoke): **1-1.5 päivää**
- Docker + CI/CD + dokumentaatio: **0.5-1 päivä**
- Viimeistely, bugifix, stabilointi: **0.5-1 päivä**

**Yhteensä: ~5.5-9 päivää** (noin **45-70 tuntia**), riippuen API-integraation valmiudesta ja datan variaatiosta.

## 6) Lopputulos (toimitettava artefakti)

Toimitetaan:
- tekninen toteutussuunnitelma PDF:nä
- selkeä ETL-arkkitehtuurikuvaus
- teknologiavalinnat perusteluineen
- realistinen aika-arvio
- riskit ja mitigointikeinot
- tuotantovalmiuden kriteerit (testit, CI, tietoturva, fallback).

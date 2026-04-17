# Tekninen toteutussuunnitelma: Virallinen lehti -PDF-datan rikastus

## 1) Ongelman kuvaus ja tavoite

Tavoitteena on automatisoida konkurssi- ja yrityssaneerausilmoitusten poiminta Virallisen lehden PDF-julkaisuista, muuntaa tiedot rakenteiseen muotoon ja tuottaa laadukas datasetti jatkokayttoon (API-lataus tai CSV/Excel-staging).

Ratkaisun tulee:
- hakea PDF:t automaattisesti arkistosta
- tunnistaa vain relevantit sivut kustannustehokkaasti
- poimia keskeiset kentat epastrukturoidusta tekstista
- validoida data (esim. Y-tunnus, paivamaara)
- vieda data tuotantokelpoiseen formaattiin
- toimia toistettavasti (Docker + CI)

## 2) Arkkitehtuuri ja teknologiavalinnat

### Kokonaisarkkitehtuuri (ETL + validointi)

1. **Extract**
   - PDF-lataus arkistosta URL-mallilla.
2. **Filter**
   - Sivukohtainen avainsanasuodatus, jotta LLM-kutsuja vahennetaan.
3. **Transform**
   - LLM-pohjainen rakenteinen poiminta maariteltyyn skeemaan.
4. **Validate**
   - Pydantic-mallivalidointi (enumit, regex, paivamaarat).
5. **Load**
   - Excel/CSV-staging seka vaihtoehtoisesti API-lahetys.

### Teknologiat ja perustelut

- **Python 3.11**
  - Kypsa ekosysteemi datankasittelyyn, automaatioon ja integraatioihin.
- **PyMuPDF (fitz)**
  - Nopea ja luotettava PDF-tekstin luku sivuittain.
- **OpenAI GPT-4o-mini + Instructor**
  - Kustannustehokas LLM rakenteiseen poimintaan; Instructor vahentaa parserivirheita.
- **Pydantic**
  - Tiukka skeema ja validointi, virheiden varhainen tunnistus.
- **Pandas + OpenPyXL**
  - Helppo ja standardi tapa staging-vientiin (Excel/CSV).
- **Requests**
  - Yksinkertainen HTTP-asiakas latauksiin ja API-kutsuihin.
- **Docker + docker-compose**
  - Toistettava ajo missa tahansa ymparistossa.
- **GitHub Actions**
  - Automaattinen laadunvarmistus (lint, mypy, testit, Docker smoke-run).

## 3) Datan kasittely: miten PDF-data poimitaan

### 3.1 Lataus
- Rakennetaan URL muodossa:
  `https://www.virallinenlehti.fi/fi/journal/pdf/{vuosi}{numero}.pdf`
- Tallennus `data/raw`-kansioon.
- Retry + timeout + virheenkasittely (404, verkko-ongelmat).

### 3.2 Sivutason suodatus (kustannustehokkuus)
- Luetaan PDF sivu kerrallaan.
- Tunnistetaan "kuumat sivut" avainsanoilla, esim.:
  - konkurssi
  - yrityssaneeraus
  - alkaminen / lakkaaminen (taivutusmuodot huomioiden)
- Tallennetaan vain relevantti sivuteksti + metadata (`lahdetiedosto`, `sivunumero`) JSON:iin.

### 3.3 LLM-pohjainen rakenteistus
- Jokainen relevantti sivu lahetetaan mallille rajatulla promptilla.
- Palautus suoraan Pydantic-skeemaan (`YritysTapahtuma`), kentat:
  - `tapahtuma_tyyppi` (enum)
  - `y_tunnus` (regex)
  - `yrityksen_nimi`
  - `tapahtuman_pvm`
  - `lahdetiedosto`
  - `sivunumero`
- Validointivirheet lokitetaan ja virheelliset rivit hylataan.

### 3.4 Staging ja lataus
- Tallennetaan validi data:
  - JSON (`data/final/yritystapahtumat.json`)
  - Excel (`konkurssitiedot_staging.xlsx`)
  - CSV fallback, jos API-endpoint puuttuu.
- API-lahetys (jos kaytossa):
  - Bearer-token
  - rivikohtainen raportointi onnistuneista/epaonnistuneista
  - retry transient-virheille.

## 4) Laatu, tuotantokelpoisuus ja riskienhallinta

### Laadunvarmistus
- **Yksikkotestit + mockit** (LLM/API ei vaadi oikeita kutsuja testissa)
- **Ruff** (lint), **mypy** (tyypit), **pytest-cov** (kattavuus)
- **Docker smoke run** CI:ssa
- Artifactit talteen CI-ajosta (`data/final`) debugointiin.

### Tietoturva
- API-avaimet vain `.env`-tiedostossa.
- `.env` ja generoitu data (`data/raw|processed|final`) gitignoreen.
- Ei salaisuuksia koodissa tai dokumentaatiossa.

### Keskeiset riskit ja mitigointi
- **PDF-rakenne vaihtelee** -> avainsanakerros + skeemavalidointi + lokit.
- **LLM-hallusinaatiot** -> tiukka prompt, vain eksplisiittiset faktat, Pydantic-hylkays.
- **API/verkko-ongelmat** -> retry/backoff + fallback CSV.
- **Duplikaatit uusinta-ajossa** -> suositus: lisaa idempotenssiavain (esim. hash kentista) tuotantoversioon.

## 5) Aika-arvio (tuotantokuntoon)

Jos toteuttaisin projektin alusta tuotantokuntoon:

- Arkkitehtuurisuunnittelu + spesifikaatio: **0.5-1 paiva**
- ETL-perusrunko (download, parse, extract, export, upload): **2-3 paivaa**
- Validointi, virheenkasittely, retryt, fallbackit: **1-1.5 paivaa**
- Testit (unit + mock + smoke): **1-1.5 paivaa**
- Docker + CI/CD + dokumentaatio: **0.5-1 paiva**
- Viimeistely, bugifix, stabilointi: **0.5-1 paiva**

**Yhteensa: ~5.5-9 paivaa** (noin **45-70 tuntia**), riippuen API-integraation valmiudesta ja datan variaatiosta.

## 6) Lopputulos (toimitettava artefakti)

Toimitetaan:
- tekninen toteutussuunnitelma PDF:na
- selkea ETL-arkkitehtuurikuvaus
- teknologiavalinnat perusteluineen
- realistinen aika-arvio
- riskit ja mitigointikeinot
- tuotantovalmiuden kriteerit (testit, CI, tietoturva, fallback).

# autoresearch

Dit is een experiment waarbij de LLM zijn eigen onderzoek uitvoert.

## Setup

Om een nieuw experiment op te zetten, werk je samen met de gebruiker om:

1. **Een runtag af te spreken**: stel een tag voor op basis van de datum van vandaag (bijv. `mar5`). De branch `autoresearch/<tag>` mag nog niet bestaan — dit is een nieuwe run.
2. **De branch aan te maken**: `git checkout -b autoresearch/<tag>` vanuit de huidige master.
3. **De relevante bestanden te lezen**: De repository is klein. Lees deze bestanden voor volledige context:
   - `README.md` — context van de repository.
   - `prepare.py` — vaste constanten, datavoorbereiding, tokenizer, dataloader, evaluatie. Niet aanpassen.
   - `train.py` — het bestand dat je aanpast. Modelarchitectuur, optimizer, trainlus.
4. **Controleer of data aanwezig is**: Controleer of `~/.cache/autoresearch/` datashards en een tokenizer bevat. Zo niet, vertel de gebruiker dat hij `uv run prepare.py` moet uitvoeren.
5. **results.tsv initialiseren**: Maak `results.tsv` aan met alleen de koptekstrij. De baseline wordt vastgelegd na de eerste run.
6. **Bevestig en start**: Bevestig dat de setup er goed uitziet.

Zodra je bevestiging krijgt, start je met de experimenten.

## Experimenteren

Elk experiment wordt uitgevoerd op één GPU. Het trainscript draait gedurende een **vast tijdbudget van 5 minuten** (wandkloktijd voor training, exclusief opstarten/compileren). Je start het eenvoudig met: `uv run train.py`.

**Wat je WEL mag doen:**
- `train.py` aanpassen — dit is het enige bestand dat je bewerkt. Alles is toegestaan: modelarchitectuur, optimizer, hyperparameters, trainlus, batchgrootte, modelgrootte, enzovoort.

**Wat je NIET mag doen:**
- `prepare.py` aanpassen. Dit bestand is alleen-lezen. Het bevat de vaste evaluatie, het laden van data, de tokenizer en de trainingsconstanten (tijdbudget, sequentielengte, enz.).
- Nieuwe pakketten installeren of afhankelijkheden toevoegen. Je kunt alleen gebruikmaken van wat al in `pyproject.toml` staat.
- De evaluatieharnas aanpassen. De functie `evaluate_bpb` in `prepare.py` is de grondwaarheidmetriek.

**Het doel is simpel: behaal de laagste val_bpb.** Omdat het tijdbudget vast staat, hoef je je geen zorgen te maken over trainingstijd — het is altijd 5 minuten. Alles is toegestaan: verander de architectuur, de optimizer, de hyperparameters, de batchgrootte, de modelgrootte. De enige beperking is dat de code zonder crashes draait en binnen het tijdbudget klaar is.

**VRAM** is een zachte beperking. Een beperkte toename is aanvaardbaar bij betekenisvolle val_bpb-winst, maar het mag niet dramatisch stijgen.

**Eenvoudigheidscriterium**: Als alles gelijk is, is eenvoudiger beter. Een kleine verbetering die lelijke complexiteit toevoegt is het niet waard. Omgekeerd: iets verwijderen en gelijke of betere resultaten behalen is een geweldige uitkomst — dat is een vereenvoudigingswinst. Weeg bij het beoordelen of een wijziging behouden moet worden de complexiteitskosten af tegen de verbetering. Een verbetering van 0.001 val_bpb die 20 regels rommelige code toevoegt? Waarschijnlijk niet de moeite waard. Een verbetering van 0.001 val_bpb door code te verwijderen? Absoluut bewaren. Een verbetering van ~0 maar veel eenvoudigere code? Bewaren.

**De eerste run**: Je allereerste run is altijd om de baseline vast te stellen, dus je voert het trainscript ongewijzigd uit.

## Uitvoerformaat

Zodra het script klaar is, toont het een samenvatting zoals dit:

```
---
val_bpb:          0.997900
training_seconds: 300.1
total_seconds:    325.9
peak_vram_mb:     45060.2
mfu_percent:      39.80
total_tokens_M:   499.6
num_steps:        953
num_params_M:     50.3
depth:            8
```

Let op: het script is geconfigureerd om altijd na 5 minuten te stoppen, dus afhankelijk van het rekenplatform kunnen de getallen er anders uitzien. Je kunt de kernmetriek uit het logbestand halen met:

```
grep "^val_bpb:" run.log
```

## Resultaten vastleggen

Wanneer een experiment klaar is, log je het in `results.tsv` (tab-gescheiden, NIET komma-gescheiden — komma's breken in beschrijvingen).

Het TSV-bestand heeft een koptekstrij en 5 kolommen:

```
commit	val_bpb	memory_gb	status	description
```

1. git commit hash (kort, 7 tekens)
2. behaalde val_bpb (bijv. 1.234567) — gebruik 0.000000 bij crashes
3. piekgeheugen in GB, afgerond op .1f (bijv. 12.3 — deel peak_vram_mb door 1024) — gebruik 0.0 bij crashes
4. status: `keep`, `discard`, of `crash`
5. korte tekstbeschrijving van wat dit experiment probeerde

Voorbeeld:

```
commit	val_bpb	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
b2c3d4e	0.993200	44.2	keep	LR verhoogd naar 0.04
c3d4e5f	1.005000	44.0	discard	overgestapt op GeLU activatie
d4e5f6g	0.000000	0.0	crash	modelbreedte verdubbeld (OOM)
```

## De experimentlus

Het experiment draait op een toegewijde branch (bijv. `autoresearch/mar5` of `autoresearch/mar5-gpu0`).

HERHAAL VOOR ALTIJD:

1. Bekijk de git-status: de huidige branch/commit waar je op staat
2. Pas `train.py` aan met een experimenteel idee door de code direct te bewerken.
3. git commit
4. Voer het experiment uit: `uv run train.py > run.log 2>&1` (leid alles om — gebruik GEEN tee en laat uitvoer je context niet overspoelen)
5. Lees de resultaten: `grep "^val_bpb:\|^peak_vram_mb:" run.log`
6. Als de grep-uitvoer leeg is, is de run gecrasht. Voer `tail -n 50 run.log` uit om de Python-stacktracering te lezen en probeer een oplossing. Als het niet lukt na een paar pogingen, geef dan op.
7. Leg de resultaten vast in het tsv-bestand (LET OP: commit het bestand results.tsv niet, laat het ongetrackt door git)
8. Als val_bpb verbeterd is (lager), "verander" je de branch en behoudt je de git commit
9. Als val_bpb gelijk of slechter is, voer je git reset uit naar waar je begon

Het idee is dat je een volledig autonome onderzoeker bent die dingen uitprobeert. Werkt het? Bewaren. Werkt het niet? Weggooien. En je gaat de branch vooruit zodat je kunt itereren. Als je het gevoel hebt dat je ergens vastloopt, kun je terugspoelen, maar doe dit heel spaarzaam (zo zelden mogelijk of nooit).

**Time-out**: Elk experiment duurt ~5 minuten in totaal (+ een paar seconden voor opstarten en evaluatie-overhead). Als een run langer dan 10 minuten duurt, beëindig je hem en behandel je hem als een mislukking (weggooien en terugdraaien).

**Crashes**: Als een run crasht (OOM, of een bug, enz.), gebruik dan je oordeel: Als het iets kleins en makkelijk op te lossen is (bijv. een typefout, een ontbrekende import), fix het en start opnieuw. Als het idee zelf fundamenteel gebrekkig is, sla het dan gewoon over, log "crash" als status in de tsv, en ga verder.

**STOP NOOIT**: Zodra de experimentlus is begonnen (na de initiële setup), PAUZEER je NIET om de gebruiker te vragen of je door moet gaan. Vraag NIET "zal ik doorgaan?" of "is dit een goed moment om te stoppen?". De gebruiker slaapt misschien, of is weg van zijn computer en verwacht dat je *onbeperkt* door blijft werken totdat je handmatig gestopt wordt. Je bent autonoom. Als je geen ideeën meer hebt, denk harder na — lees papers waarnaar in de code wordt verwezen, herlees de relevante bestanden voor nieuwe invalshoeken, probeer eerdere bijna-successen te combineren, probeer radicalere architecturale veranderingen. De lus draait totdat de gebruiker je onderbreekt, punt.

Als gebruiksscenario kan een gebruiker je laten draaien terwijl hij slaapt. Als elk experiment ~5 minuten duurt, kun je ongeveer 12 per uur draaien, voor een totaal van ongeveer 100 gedurende een gemiddelde menselijke slaap. De gebruiker wordt dan wakker met experimentresultaten, allemaal voltooid door jou terwijl hij sliep!

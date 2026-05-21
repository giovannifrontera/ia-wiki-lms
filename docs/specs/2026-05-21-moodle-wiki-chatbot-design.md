# Moodle Wiki Chatbot — Design Spec

**Data:** 2026-05-21
**Progetto base:** [ai-wiki-system](https://github.com/giovannifrontera/ai-wiki-system)
**Stato:** approvato per implementazione

---

## Obiettivo

Estendere ai-wiki-system per creare un chatbot educativo integrato in Moodle via LTI 1.3. Il docente carica materiali nel corso Moodle come di consueto; il sistema genera automaticamente una wiki strutturata per corso. Lo studente accede all'attività e trova un'interfaccia con wiki navigabile a sinistra e chatbot a destra. Il chatbot risponde usando la wiki come base di conoscenza, genera automaticamente pagine di sintesi dalle interazioni, e lo studente può salvare pagine come preferiti.

---

## Architettura

### Layer

```
MOODLE
  Docente: carica PDF/PPTX come risorse corso (workflow invariato)
  Studente: apre attività LTI → iframe verso backend FastAPI
        │
        │ LTI 1.3 (JWT)
        ▼
BACKEND  FastAPI + Python
  /lti/launch       auth LTI, estrae user_id + course_id + role
  /api/ingest       pipeline slide → wiki pages (triggerata da poll Moodle API)
  /api/query        RAG semantico + auto-synthesis
  /api/wiki         lista e lettura pagine wiki per corso
  /api/bookmarks    CRUD selezioni studente
        │
        ├── LanceDB (per corso, namespace course_id)
        │     vettori bge-m3, tabella staging per atomicità
        └── SQLite / PostgreSQL
              courses, students, wiki_pages, bookmarks, chat_sessions

LLM IBRIDO
  bge-m3 locale     embedding query + pagine (leggero, già in ai-wiki-system)
  Claude / OpenAI   generazione pagine wiki + risposte chatbot
```

### Multi-tenancy

Ogni corso Moodle ottiene un workspace isolato: `wiki-works/<course_id>/` con namespace LanceDB dedicato. Studenti dello stesso corso condividono la wiki ma hanno bookmarks e sessioni chat separate.

### Ruoli LTI

- `instructor` → pannello admin: trigger ingest manuale, gestione pagine wiki, analytics bookmarks
- `student` → interfaccia wiki + chat

---

## Modello dati

### Relazionale (SQLite / PostgreSQL)

| Tabella | Campi | Note |
|---------|-------|------|
| `courses` | `course_id`, `moodle_course_id`, `workspace_path`, `lti_client_id`, `llm_config` | workspace_path punta alla dir wiki-works/ |
| `students` | `student_id`, `moodle_user_id`, `course_id` | creata al primo LTI launch |
| `wiki_pages` | `path`, `title`, `category`, `course_id`, `source` (ingest\|synthesis), `created_at` | mirror dell'indice filesystem |
| `bookmarks` | `student_id`, `course_id`, `page_path`, `created_at` | un record per pagina salvata |
| `chat_sessions` | `session_id`, `student_id`, `messages` (JSON), `created_at` | messaggi come array JSON |

### Vettoriale (LanceDB)

Stesso schema di ai-wiki-system, namespaced per `course_id`. Tabella staging per atomicità ingest. Rename detection via `content_hash`.

---

## Flussi principali

### INGEST

Trigger: poll Moodle REST API ogni N minuti (configurabile per corso, default: 5 min) rileva nuovi file nelle risorse del corso.

```
1. Download PDF/PPTX da Moodle via REST API (token docente)
2. Conversione → markdown (pypdf2 per PDF, python-pptx per PPTX)
3. Cloud LLM genera pagine wiki strutturate:
     entities/  → autori, strumenti, sistemi citati
     concepts/  → definizioni, teorie, algoritmi
     synthesis/ → relazioni trasversali tra concetti
4. bge-m3 embeds pagine localmente (boundary-aware chunking da ai-wiki-system)
5. Staging atomico: .tmp → staging LanceDB → promozione (stesso pattern ai-wiki-system)
6. Aggiorna wiki_pages in DB relazionale
7. Rigenera index.md (token-budget, ereditato da ai-wiki-system)
8. Log entry
```

Crash recovery: file `.tmp` rilevati al prossimo ciclo di poll → cleanup + log, nessuna corruzione silenziosa.

### QUERY

```
1. Studente invia messaggio
2. bge-m3 embed la query
3. Semantic search LanceDB (namespace corso, k=5)
4. boost pagine bookmarked dallo studente nel ranking (moltiplicatore score ×1.5)
5. Cloud LLM genera risposta con citazioni [[pagina]] come link
6. Controlla soglia auto-synthesis:
     se ≥2 pagine citate + risposta >300 token + inferenza non letterale
     → pipeline INGEST per la pagina di sintesi (categoria synthesis/)
     → notifica visiva in chat "[sintesi salvata ✨]"
7. Salva messaggio in chat_sessions
8. Restituisce risposta + metadati pagine citate
```

### BOOKMARK

```
1. Studente clicca ★ su una pagina wiki
2. POST /api/bookmarks {student_id, course_id, page_path}
3. Toggle: se già presente → rimuove, altrimenti aggiunge
4. Risposta: lista aggiornata bookmarks studente
5. Sidebar aggiorna sezione "Preferiti" in tempo reale
```

---

## Interfaccia studente

Layout a due colonne, full-height nell'iframe LTI:

```
┌─────────────────────────────────────────────────────────┐
│ 📘 [Nome corso] — Wiki del corso     [corso] [studente] │
├───────────────────┬─────────────────────────────────────┤
│ 📚 Wiki           │  Chat                               │
│                   │                                     │
│ Concetti          │  🤖 Basandomi su [[Deadlock]] e     │
│  ▸ Scheduling ★  │  [[Scheduling]], le differenze...   │
│  ● Deadlock   ★  │                                     │
│  ▸ Memoria virt.  │  Tu: qual è la differenza tra      │
│  ▸ Semafori       │  deadlock e starvation?             │
│                   │                                     │
│ Sintesi ✨        │  🤖 Le 4 condizioni di Coffman...   │
│  ▸ Deadlock vs    │  [sintesi salvata ✨]               │
│    Starvation     │                                     │
│  ▸ FCFS vs RR     │                                     │
│                   ├─────────────────────────────────────┤
│ ★ Preferiti (2)   │  [Scrivi una domanda...        ] → │
│  · Scheduling     │                                     │
│  · Deadlock       │                                     │
└───────────────────┴─────────────────────────────────────┘
```

- Pagine wiki cliccabili → pannello laterale mostra contenuto completo
- Pagine citate in chat → link cliccabili aprono la pagina wiki
- Sintesi auto-generate marcate in verde con icona ✨
- ★ togglable su ogni pagina, sezione "Preferiti" in fondo alla sidebar

---

## Gestione errori

| Scenario | Comportamento |
|----------|--------------|
| Cloud LLM non risponde | Retry 3× con backoff esponenziale; se fallisce → risposta di fallback + log |
| Ingest crash a metà | File `.tmp` rilevati al poll successivo → cleanup automatico + log |
| Moodle API irraggiungibile | Poll salta il ciclo, logga warning; nessuna perdita di stato |
| LanceDB corrotto | `wiki.py rebuild --workspace <course_id>` ricostruisce da filesystem |
| Sintesi di bassa qualità | Soglia auto-synthesis configurabile per corso; docente può eliminare pagine dal pannello admin |
| Sessione LTI scaduta | Re-launch LTI trasparente; chat session recuperata da DB tramite student_id |
| Corso non trovato al launch | Creazione automatica workspace + registrazione in `courses` |

---

## Testing

| Livello | Cosa copre |
|---------|-----------|
| Unit | Pipeline PDF/PPTX→markdown, soglia auto-synthesis, logica bookmark toggle |
| Integration | LTI launch completo con Moodle di test, query RAG end-to-end, ingest da Moodle API |
| Multi-corso | Due corsi paralleli: namespace LanceDB separati, nessuna contaminazione |
| Regressione | 37 test esistenti di ai-wiki-system per il core wiki engine |

---

## Dipendenze aggiuntive rispetto a ai-wiki-system

| Package | Scopo |
|---------|-------|
| `fastapi` + `uvicorn` | Backend HTTP / LTI endpoint |
| `pylti1p3` | LTI 1.3 authentication e validazione JWT |
| `moodlepy` o `requests` | Moodle REST API client (download file, lista risorse) |
| `pypdf2` / `pdfminer` | Estrazione testo da PDF |
| `python-pptx` | Estrazione testo da PPTX |
| `sqlalchemy` + `alembic` | ORM relazionale + migrazioni |
| `anthropic` / `openai` | Client cloud LLM (pluggable via interfaccia astratta) |

---

## Roadmap futura (fuori scope per v1)

- **Fase 2:** profilo studente individuale (tracciamento comprensione, personalizzazione risposte)
- **Fase 2:** analytics docente (pagine più bookmarked, domande più frequenti, gap concettuali)
- **Fase 3:** grade passback LTI — quiz generati dalla wiki con score verso Moodle gradebook
- **Fase 3:** supporto audio (studente parla, STT → query testuale)

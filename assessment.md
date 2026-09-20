# DOTMappers IT Pvt. Ltd. | AI Engineer Assessment End-to-End AI System Sprint[cite: 1, 2]

## End-to-End AI System Sprint
Technical Assessment — AI Engineer Role[cite: 1, 2]  
DOTMappers IT Pvt. Ltd.[cite: 1, 2]

| Duration | Format | Submission | Walkthrough |
| :--- | :--- | :--- | :--- |
| 48 Hours[cite: 1, 2] | GitHub Repository[cite: 1, 2] | GitHub link + README[cite: 1, 2] | 30 min post-submission[cite: 1, 2] |

---

## 1. Overview
This assessment evaluates your ability to independently architect, build, and deliver a working AI system — from a problem statement to a functional prototype — within a 48-hour window[cite: 1, 2]. This mirrors what is expected of the AI Engineer role at DOTMappers: translating a business problem into a production-grade AI solution with minimal handholding[cite: 1, 2].

---

## 2. Problem Statement
You are given a customer support ticket dataset (CSV)[cite: 1, 2]. Build an AI-powered system that does all the following[cite: 1, 2]:

* Ingest the CSV data and make it queryable[cite: 1, 2].
* Answer natural language questions about the data (e.g., "How many critical tickets are unresolved?", "Which agent has the lowest average customer rating?")[cite: 1, 2].
* Detect and flag anomalies (e.g., tickets with abnormally long resolution times, unresolved high-priority tickets older than 24 hours)[cite: 1, 2].
* Expose the functionality via a REST API AND a minimal UI — Both are required[cite: 1, 2].

The system must use an LLM for natural language understanding[cite: 1, 2]. You may use any free-tier or locally run model (Ollama, Groq free tier, Hugging Face Inference API, etc.)[cite: 1, 2].

---

## 3. Dataset

### 3.1 File Provided
* **Filename**: `support_tickets.csv`[cite: 1, 2]
* **Total Rows**: 500[cite: 1, 2]
* **Format**: UTF-8 CSV[cite: 1, 2]

### 3.2 Schema Preview[cite: 1, 2]
| ticket_id | created_at | category | priority | status | resp_time_hrs | resol_time_hrs | agent_id | cust_rating | issue_summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TKT-001[cite: 1, 2] | 2024-01-03 09:12[cite: 1, 2] | Billing[cite: 1, 2] | High[cite: 1, 2] | Resolved[cite: 1, 2] | 0.5[cite: 1, 2] | 2.3[cite: 1, 2] | AGT-04[cite: 1, 2] | 4[cite: 1, 2] | Incorrect charge on invoice[cite: 1, 2] |
| TKT-002[cite: 1, 2] | 2024-01-03 11:45[cite: 1, 2] | Technical[cite: 1, 2] | Critical[cite: 1, 2] | Escalated[cite: 1, 2] | 1.2[cite: 1, 2] | 18.5[cite: 1, 2] | AGT-07[cite: 1, 2] | 2[cite: 1, 2] | Login failure after update[cite: 1, 2] |
| TKT-003[cite: 1, 2] | 2024-01-04 08:30[cite: 1, 2] | General[cite: 1, 2] | Low[cite: 1, 2] | Resolved[cite: 1, 2] | 3.1[cite: 1, 2] | 5.0[cite: 1, 2] | AGT-02[cite: 1, 2] | 5[cite: 1, 2] | Request for product docs[cite: 1, 2] |
| TKT-004[cite: 1, 2] | 2024-01-04 14:22[cite: 1, 2] | Technical[cite: 1, 2] | High[cite: 1, 2] | Resolved[cite: 1, 2] | 0.8[cite: 1, 2] | 4.7[cite: 1, 2] | AGT-04[cite: 1, 2] | 3[cite: 1, 2] | API timeout in production[cite: 1, 2] |
| TKT-005[cite: 1, 2] | 2024-01-05 10:05[cite: 1, 2] | Billing[cite: 1, 2] | Medium[cite: 1, 2] | Open[cite: 1, 2] | 2.0[cite: 1, 2] | NULL[cite: 1, 2] | AGT-09[cite: 1, 2] | NULL[cite: 1, 2] | Refund not processed[cite: 1, 2] |

### 3.3 Column Descriptions[cite: 1, 2]
| Column | Type | Description |
| :--- | :--- | :--- |
| `ticket_id`[cite: 1, 2] | String[cite: 1, 2] | Unique ticket identifier[cite: 1, 2] |
| `created_at`[cite: 1, 2] | Datetime (YYYY-MM-DD HH:MM)[cite: 1, 2] | Ticket creation timestamp[cite: 1, 2] |
| `category`[cite: 1, 2] | String (Billing / Technical / General)[cite: 1, 2] | Issue category[cite: 1, 2] |
| `priority`[cite: 1, 2] | String (Low / Medium / High / Critical)[cite: 1, 2] | Ticket urgency level[cite: 1, 2] |
| `status`[cite: 1, 2] | String (Open / Resolved / Escalated)[cite: 1, 2] | Current ticket status[cite: 1, 2] |
| `resp_time_hrs`[cite: 1, 2] | Float[cite: 1, 2] | Hours from creation to first agent response[cite: 1, 2] |
| `resol_time_hrs`[cite: 1, 2] | Float (null if unresolved)[cite: 1, 2] | Hours from creation to resolution[cite: 1, 2] |
| `agent_id`[cite: 1, 2] | String[cite: 1, 2] | Assigned support agent identifier[cite: 1, 2] |
| `cust_rating`[cite: 1, 2] | Integer 1–5 (null if unresolved)[cite: 1, 2] | Post-resolution satisfaction rating[cite: 1, 2] |
| `issue_summary`[cite: 1, 2] | String (free text)[cite: 1, 2] | Brief description of the issue reported[cite: 1, 2] |

---

## 4. Deliverables
Your GitHub repository must include all the following[cite: 1, 2]:
1. Working system fulfilling all four requirements in Section 2[cite: 1, 2].
2. REST API (FastAPI or equivalent) with at least 3 endpoints — NL query, anomaly detection, health check — AND a minimal UI (Streamlit, Gradio, or similar) covering the same functionality[cite: 1, 2].
3. README.md covering: setup instructions, architecture overview, model/tools used, example queries with outputs, known limitations[cite: 1, 2].
4. requirements.txt or equivalent so the evaluator can run the system locally[cite: 1, 2].

---

## 5. Technical Constraints
* **Language**: Python only[cite: 1, 2].
* **LLM**: Must use an LLM for NL query handling[cite: 1, 2]. Allowed: Ollama (local), Groq free tier, Hugging Face Inference API free tier, or any locally runnable model[cite: 1, 2].
* **Zero Cost**: No paid APIs or services[cite: 1, 2]. The evaluator must be able to run your system at zero cost[cite: 1, 2].
* **Startup**: The system must start with a single command (e.g., `docker-compose up`, `run.bat`, or `uvicorn main:app`)[cite: 1, 2].

---

## 6. Evaluation Criteria
| Criterion | What We Look For | Weight |
| :--- | :--- | :--- |
| **Functionality**[cite: 1, 2] | All 4 requirements work as described[cite: 1, 2] | 30%[cite: 1, 2] |
| **Architecture & Design**[cite: 1, 2] | Component choices are reasoned, not accidental[cite: 1, 2] | 25%[cite: 1, 2] |
| **Code Quality**[cite: 1, 2] | Clean, modular, readable, with error handling[cite: 1, 2] | 20%[cite: 1, 2] |
| **LLM Integration Quality**[cite: 1, 2] | Prompt design, output structuring, edge case handling[cite: 1, 2] | 15%[cite: 1, 2] |
| **README & Documentation**[cite: 1, 2] | Clear setup, architecture explanation, example outputs[cite: 1, 2] | 10%[cite: 1, 2] |

---

## 7. Timeline
| Phase | Time Window | Focus |
| :--- | :--- | :--- |
| **Planning**[cite: 1, 2] | Hours 0–4[cite: 1, 2] | Read brief, design architecture, choose tools and LLM[cite: 1, 2] |
| **Core Pipeline**[cite: 1, 2] | Hours 4–16[cite: 1, 2] | Data ingestion, LLM integration, NL query handling, anomaly logic[cite: 1, 2] |
| **API / UI Layer**[cite: 1, 2] | Hours 16–32[cite: 1, 2] | Expose endpoints or UI, input validation, error handling[cite: 1, 2] |
| **Polish & Submit**[cite: 1, 2] | Hours 32–48[cite: 1, 2] | Testing, README, code cleanup, GitHub submission[cite: 1, 2] |

---

## 8. Submission Instructions
* Share your GitHub repository link via email to: `RajathKumar@dotmappers.in`[cite: 1, 2]
* **Subject line**: `[AI Engineer Assessment] - Your Name`[cite: 1, 2]
* **Deadline**: 48 hours from the time this document is received[cite: 1, 2].
* A 30-minute architecture walkthrough call will be scheduled after submission[cite: 1, 2].

---

## 9. Sample Queries
The following are indicative queries your system should handle[cite: 1, 2]. The evaluator will use their own queries during the walkthrough[cite: 1, 2]:
1. "How many tickets are currently open?"[cite: 1, 2]
2. "Which agent resolved the most tickets this month?"[cite: 1, 2]
3. "Show me all Critical tickets not resolved within 12 hours."[cite: 1, 2]
4. "What is the average customer rating for Technical category tickets?"[cite: 1, 2]
5. "Are there any anomalies in resolution times this week?"[cite: 1, 2]

---

## 10. Notes
This assessment is intentionally open-ended[cite: 1, 2]. There is no single correct architecture[cite: 1, 2]. You will be evaluated on the reasoning behind your choices as much as the working code[cite: 1, 2]. The 30-minute post-submission walkthrough is your opportunity to explain trade-offs, what you would improve with more time, and how you would scale the system[cite: 1, 2].

Good luck[cite: 1, 2].
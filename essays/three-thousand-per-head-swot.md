# $3,000 a head: the purchasing-power case for personal, local models

SWOT in two parts. October 23, 2026. Findings only; no verdict.

**The proposal as set by the author.** Government spending power of $3,000 per citizen per year, about $1 trillion a year, creates demand for localized models: models that run on the person's own device, hold the person's data locally, and are tuned to that person's learning disability, health complications and emotional complexities. The purpose is fit for each person without exposure to an open network rampant with abuse. The payment channel (individual payments or large government payments) is not the deciding variable, because both carry fraud; fraud is treated here as a constant.

**How this was built.** Five independent analyst passes (fiscal, security and privacy architecture, policy feasibility, data dignity and civil liberties, red team), each required to source every point, followed by an adversarial re-check of each pass's load-bearing figures. Corrections from the re-check are applied below. Items the checkers could not re-source are marked (unverified). Part 2 (sections 7 to 14) adds three fit lenses, built the same way: special education, health and mental health, and the technical economics of tuning a model to one person.

## 1. Scale

| Measure | Figure | Source |
| --- | --- | --- |
| US residents, July 1, 2025 | 341.8 million | Census Vintage 2025 |
| $3,000 × residents | $1.025 trillion a year | arithmetic |
| Citizens only (22 to 26 million noncitizens excluded, estimate) | about $0.95 trillion a year | arithmetic on Census and DHS estimates |
| Federal outlays, FY2025 | $7.01 trillion; the program is 14.6% of it | Treasury Combined Statement FY2025 |
| Medicare, FY2025 | $997 billion | CBO Monthly Budget Review, FY2025 final |
| National defense, FY2025 | $917 billion | CBO |
| Net interest, FY2025 | about $970 billion | CBO |
| GDP, 2025 | $30.8 trillion; the program is 3.3% of it | BEA |
| FY2026 deficit, baseline | $1.9 trillion, 5.8% of GDP; debt held by the public 101% of GDP, rising to 120% by 2036 | CBO, February 2026 |
| Four largest cloud companies, 2026 capital spending | Company guidance of February 2026 sums to roughly $650 to $700 billion; trackers citing July 2026 revisions report $720 to $745 billion (unverified). About $1,900 to $2,100 per resident | company earnings calls; aggregator trackers |
| Largest per-person federal disbursement to date | 476 million Economic Impact Payments, $814 billion, March 2020 to March 2021 | IRS, as of Dec 31, 2021 |
| Only US universal per-resident dividend | Alaska Permanent Fund Dividend: $1,702 (2024), $1,000 (2025), $1,200 (2026); peak $3,284 (2022) | Alaska Department of Revenue |

## 2. What $3,000 a year buys per person (October 2026 prices, estimates)

| Component | Annual cost per person | Basis |
| --- | --- | --- |
| Phone-class device for a 3-billion-parameter model | $0 for the 91% of adults who already own a smartphone; iPhone 17 from $799 with 8 GB | Pew Research, 2025; Apple |
| Device for 30 to 70 billion parameter models | $615 (Framework Desktop 128 GB, $2,459, over 4 years) to $1,275 (Mac Studio 128 GB, about $5,100, over 4 years) | vendor prices; Framework raised the desktop from $1,999 in early 2026 after DRAM contract prices roughly doubled in Q1 2026 (TrendForce) |
| Electricity for local inference | $21 to $96 at 18.2 cents per kWh (160 to 240 W, 2 to 6 hours a day) | EIA 2026 residential price; corrected arithmetic |
| Per-person share of a public open-weight frontier model | $3 to $30 (a $1 billion run is $2.93 per resident; a $10 billion-a-year program is $29) | Epoch AI; Llama 3.1 405B used about 31 million GPU-hours, roughly $60 to $80 million of compute |
| Support and maintenance | $100 to $200 | estimate |
| Data-dignity payment benchmark | about $300 (Meta's US and Canada revenue per person, 2025); Lanier and Weyl's 2018 estimate for data as labor was about $5,000 per person | Meta earnings; Harvard Business Review, Sept 26, 2018 |
| Comparison: hosted services | ChatGPT Plus or Claude Pro, $240 a year; $3,000 buys 15 billion tokens a year of hosted Llama 70B at $0.20 per million | July and Sept 2026 price lists |
| **Stack total** | **about $400 (phone tier) to $2,000 (70B tier with a data payment)** | sum |
| **Headroom for the personalization layer and human review** | **about $1,000 to $2,600 per person per year** | $3,000 minus the stack; part 2 prices this layer |

## 3. SWOT

### Strengths

- **The payment rail exists at this scale.** The IRS delivered 476 million payments worth $814 billion in a year; Social Security pays about 70 million people every month. Delivery is not the binding constraint.
- **Local inference is shipped product.** Apple runs a roughly 3-billion-parameter model on the phone; OpenAI's gpt-oss-20b (August 2025, Apache 2.0) runs in 16 GB; Hugging Face hosts more than 3 million public models (August 2026).
- **A plural, open supply exists outside the four largest companies.** DeepSeek R1 (MIT license, January 2025), gpt-oss (August 2025), Switzerland's Apertus 8B and 70B (fully open weights, data and recipes, September 2, 2025), Meta's Muse Glimmer 30B (Apache 2.0, August 10, 2026).
- **Localization removes the single honeypot.** Gravy Analytics was breached in January 2025 through one misappropriated cloud key, exposing more than 30 million location points from thousands of apps. Data on a person's own device sits under Riley v. California (2014), which requires a warrant; data on a vendor's server sits under the third-party doctrine.
- **A buyer of 340 million units sets terms.** GSA's OneGov deals priced ChatGPT Enterprise and Claude at $1 per agency in August 2025; Medicare sets provider prices by reference. Open weights, no telemetry and provenance can be conditions of sale.
- **Verification tooling is in production.** Apple Private Cloud Compute publishes code measurements to a transparency log (October 2024); Sigstore model-signing v1.0 (April 2025) signs weights into a public log; Estonia's X-Road has run federated, citizen-visible data access for two decades.
- **Per-resident payments without behavioral data have a 40-year precedent.** Alaska's dividend is keyed to residency, not usage, since 1982.
- **Training data has a court-set price and payment rails.** Bartz v. Anthropic: $1.5 billion for 482,460 works, about $3,100 per book, final approval July 21, 2026. Cloudflare Pay per Crawl (July 2025) and the RSL licensing standard (September 2025) exist to route per-use payments.
- **Public trust already sits with localization and with states.** The Senate stripped the state-AI-law moratorium 99 to 1 on July 1, 2025; 55% of 2024 voters opposed it against 18% in favor (IFS/YouGov, 2025).

### Weaknesses

- **Scale.** $1.025 trillion a year exceeds Medicare, defense and net interest individually and equals 14.6% of federal outlays, 3.3% of GDP, on top of a 5.8%-of-GDP deficit.
- **Cost-to-serve gap.** The hardware, power, model and support stack costs $400 to $2,000 a year; $3,000 leaves $340 to $680 billion a year (estimate) that must be absorbed by the personalization layer or becomes surplus to vendors.
- **Unit mismatch.** An annual cash flow against a 2.5-year phone cycle and a 4-year desktop cycle; a per-citizen unit pays for infants and for the 91% of adults who already own the phone-class device.
- **Hardware cannot be bought at today's prices at this volume.** DRAM contract prices roughly doubled in Q1 2026 (TrendForce); Micron expects meaningful new supply only in 2027 to 2028; SK Hynix has signaled shortage conditions possibly through 2030; Dell and Lenovo signaled 15 to 20% PC price increases.
- **The endpoint is the least-defended node.** One infostealer family infected more than 394,000 Windows machines in two months (Microsoft, May 2025); KELA counted 4.3 million infostealer-infected devices in 2024; Cisco Talos found 1,139 unauthenticated Ollama servers exposed within minutes (September 2025).
- **"Localized" is undefined, and shipping defaults are cloud sync.** Windows 11 auto-enabled OneDrive folder backup during setup (June 2024) and uploads BitLocker recovery keys to the Microsoft account by default (24H2); iCloud Backup is on by default.
- **Open weights are not auditability.** A hash proves which file is on the device, not what is inside it: Anthropic's Sleeper Agents paper (January 2024) showed backdoors that survive fine-tuning; HiddenLayer's ShadowLogic (October 2024) showed graph-level backdoors in ONNX models.
- **The update tail is unfunded.** Windows 10 reached end of support on October 14, 2025 with about 40% of Windows PCs still on it; Canalys estimated 240 million PCs could not move to Windows 11.
- **Frontier open supply is narrowing.** Meta's Muse Spark (April 8, 2026) was its first closed-weight frontier model; Llama 4 Behemoth never shipped; the leading open weights now come from Chinese labs and OpenAI's discretion.
- **The money flows the wrong way for data dignity.** Lanier's remedy is payment from model operators to the people whose work trained the model; here money flows from the Treasury to device and model vendors.
- **No right to be forgotten inside weights.** Apertus handles deletion requests with a hash file for an output filter every six months, not by retraining; consent has to be ex ante.
- **Administrative capacity is shrinking.** The IRS lost 25.9% of its workforce between January and June 2025; opt-in tech subsidies reach a minority (ACP take-up 28 to 43% of eligible households).
- **Identity rails are rejected when tried.** The IRS abandoned mandatory ID.me facial recognition in February 2022; the UK's mandatory digital ID drew a petition past 2 million signatures within days (September 2025).
- **Literacy.** PIAAC 2023: 28% of US adults at literacy level 1 or below; about 1 in 8 adults over 65 does not use the internet.

### Opportunities

- **Household unit.** 134.8 million households × $3,000 = $404 billion; an in-kind 128 GB-class device on a four-year cycle plus a $300 service tier is about $120 billion a year, 12% of the per-citizen figure.
- **Means-tested rails already run.** Lifeline's National Verifier (since 2018) and the ACP enrollment base; equipping the roughly 40 million households without a capable machine is about $25 billion a year on a four-year cycle.
- **Fund the model as a public good.** A $5 to $10 billion-a-year public open-weight program is $15 to $30 per person and would be among the largest in the world (EU InvestAI gigafactory fund €20 billion; IndiaAI Mission about $1.2 billion; OpenEuroLLM €37 million; NSF's NAIRR pilot).
- **Citizen-held voucher against a published spec.** Open weights, offline-capable, reproducible hash; the citizen chooses the model, not an agency. GSA added ChatGPT, Gemini and Claude to the federal schedule in August 2025; flipping the chooser is the structural change.
- **Provenance royalty pool through data unions.** 5% of $1.02 trillion is $51 billion a year, about 34 Anthropic settlements every year, paid through Lanier's mediators of individual data and priced off the court benchmark. The EU AI Act's training-content summary (Article 53) applies to models placed on the EU market from August 2, 2025.
- **Statutory right to exit.** Weights, fine-tunes and memory files exportable; the EU Data Act caps cloud switching charges now and bans them from January 12, 2027.
- **Signed, hash-pinned weights with public system prompts and opt-in updates.** On May 14, 2025 one unauthorized system-prompt change made Grok inject "white genocide" claims into unrelated answers for hours; xAI's remedy was to publish its prompts.
- **A funding rail that cannot lapse by appropriation.** The Universal Service Fund mechanism (about $8 billion a year) was upheld 6 to 3 on June 27, 2025; Lifeline, funded that way, did not lapse while the appropriated ACP did.
- **The security baseline lever.** Conditioning eligibility on attestation, signed updates and a 10-year patch tail; the EU Cyber Resilience Act's vulnerability-reporting duties apply from September 11, 2026.
- **The device as the passkey anchor.** More than 97% of identity attacks are password-based (Microsoft Digital Defense Report 2025); an attested device per person is phishing-resistant MFA.
- **States as the administering layer with error-rate cost share.** The 2025 reconciliation law shifts SNAP costs to states by payment-error rate from FY2028; 22 states have privacy laws.
- **Pilot shape that passes.** Estonia's AI Leap gave 20,000 students and 3,000 teachers AI tools from September 1, 2025 and expanded by 38,000 students in September 2026; a two-state randomized pilot in the US would cost under $1 billion.
- **Index the benefit to falling inference prices.** Cost per token at constant capability has fallen about 10 times a year (a16z); the open-closed gap on Chatbot Arena narrowed from 8.0% to 1.7% between January 2024 and February 2025 (Stanford AI Index 2025).
- **Public opinion.** Pew (June 2026): 52% of Americans are more concerned than excited about AI, 71% expect fewer jobs. "Your model, your data, on your device" addresses the 52%.

### Threats

- **Supplier capture.** Nvidia's gross margin was 75.0% in the quarter ended January 2026; subsidies in concentrated markets are priced in, not passed through (EV credits: 70 to 100% captured by recipients only where markets were competitive; about 60 cents of each dollar of added student-loan limits passed through to tuition).
- **Fraud, held constant across channels.** GAO's pandemic unemployment estimate of 11 to 15% applied to $1.025 trillion is $113 to $154 billion a year; EITC improper payments ran about 33% (unverified for FY2025); GAO could not verify 36% of sampled Lifeline subscribers (2017); government-wide improper payments were $162 billion in FY2024.
- **Lapse.** ACP ended June 1, 2024; the 2021 Child Tax Credit expansion lasted one year; the EV credit ended September 30, 2025; the Senate rescinded CPB's $1.1 billion advance appropriation 51 to 48 on July 17, 2025; the $2.75 billion Digital Equity Act programs were ended by executive action in May 2025.
- **The state as the new Siren Server.** Executive Order 14319 (July 23, 2025) bars agencies from buying models that fail "Unbiased AI Principles," with an OMB implementing memo of December 11, 2025; China's generative-AI filing registry; the UK forced Apple to withdraw Advanced Data Protection for UK users on February 21, 2025; the IRS shared about 47,000 taxpayer addresses with ICE in 2025, found unlawful by a district court in February 2026.
- **Chilling effects.** After the June 2013 surveillance revelations, views of surveillance-sensitive Wikipedia articles fell 20 to 30% (Penney, 2016). A subsidized model believed to log or report stops being asked about health, immigration or politics.
- **The update channel as a single point of failure.** CrowdStrike's July 19, 2024 content push took down about 8.5 million Windows devices in hours; the xz-utils backdoor (March 2024) reached release tarballs after a two-year social-engineering campaign and was caught by one engineer noticing a slowdown.
- **Targeted compromise survives any architecture.** Pegasus zero-click exploits; a jury awarded WhatsApp $167 million against NSO on May 6, 2025; TEE.fail (October 2025) extracts attestation keys from fully updated machines with a sub-$1,000 interposer.
- **The apps around the model keep harvesting.** SDK-level data brokerage continued for years before the FTC's Gravy Analytics order (January 2025); the EU's first DMA fines (April 2025) were €500 million and €200 million against firms with hundreds of billions in revenue.
- **Interest-rate feedback.** CBO's higher-rate scenario (+150 basis points) lifts 2036 debt to 133% of GDP from 120%; a $1 trillion line on top plausibly reaches 145 to 150% (estimate).
- **Buying at the top of the memory cycle, with tariffs.** Shortage conditions through 2027 to 2030; a January 2026 Section 232 proclamation put a 25% tariff on certain advanced computing chips and derivative products; laptop and phone status pending.
- **Open supply routes to adversary-trained models.** With Meta closed, leading open weights are DeepSeek and Qwen; the No Adversarial AI Act was introduced in June 2025 and several states barred DeepSeek on government devices.
- **Defaults beat ideology.** ChatGPT passed 900 million weekly users in February 2026 (company-stated); EU choice screens (March 2024) left Google's EU search share near 90%.
- **Federal preemption of the plural layer.** The December 11, 2025 executive order directs an AI Litigation Task Force against state AI laws and conditions remaining broadband funds.
- **Per-enrollee payments to vendors get gamed.** Medicare Advantage: $84 billion, or 20%, more than traditional Medicare for the same enrollees in 2025 (MedPAC, March 2025).

## 4. Constants, as set by the author

Fraud is not a deciding variable between individual payments and large government payments; the rates above apply to either channel. The figures to carry: 11 to 15% (pandemic unemployment, GAO), 18.5% (Lifeline improper-payment rate, dated), 33% (EITC), $162 billion government-wide (FY2024).

## 5. Figure-check ledger

| Lens | Figures re-checked | Confirmed | Corrected | Could not re-source in time |
| --- | --- | --- | --- | --- |
| Fiscal | 19 | 10 | 3 | 6 |
| Security and privacy | 14 | 7 | 2 | 5 |
| Policy feasibility | 8 | 4 | 0 | 4 |
| Data dignity and civil liberties | 8 | 5 | 2 | 1 |
| Red team | 10 | 6 | 4 | 0 |
| **Total** | **59** | **32** | **11** | **16** |

Corrections applied above: the four companies' 2026 capital spending is "guidance" only at $650 to $700 billion (the $720 to $745 billion range comes from trackers); local-inference electricity is $21 to $96 a year, not $36 to $90; the 341.8 million base is residents, not citizens; the CPB rescission passed the Senate 51 to 48, not 51 to 49; Canalys's 240 million figure counts PCs, not users; the EU training-content summary applies to models placed on the market from August 2, 2025, not to all models on that date; the Anthropic settlement works count is 482,460; the roughly $20 billion Google paid Apple for default placement is a 2022 figure, separate from the $26.3 billion 2021 total; the "$410 billion in 2025" capex figure is aggregator math, not a filing; ChatGPT's 900 million weekly users is a company-stated metric reported secondhand. Figures marked (unverified) or (estimate) in the text are the ones the checkers could not re-source; the fiscal-lens DRAM and device prices for late 2026 are among them.

## 6. Sources (principal)

Census Bureau, Vintage 2025 population estimates (Jan 27, 2026); Treasury, Combined Statement FY2025; CBO, Monthly Budget Review FY2025 and Budget and Economic Outlook, Feb 2026; BEA, GDP 2025; IRS, Economic Impact Payment totals (Dec 31, 2021); Alaska Department of Revenue, PFD history; Pew Research, Mobile Fact Sheet 2025 and AI attitudes survey (June 2026); EIA, Short-Term Energy Outlook 2026; TrendForce DRAM contract price reports, Q1 and Q2 2026; Epoch AI, cost of frontier models and R&D versus training compute (Mar 23, 2026); GAO-23-106696 (Sept 12, 2023) and GAO-25-107753 (Mar 11, 2025); GAO Lifeline review (May 2017); FCC v. Consumers' Research (June 27, 2025); Riley v. California (2014); Carpenter v. United States (2018); Bartz v. Anthropic settlement orders (Sept 25, 2025; July 21, 2026); Lanier and Weyl, HBR (Sept 26, 2018); Apple, Private Cloud Compute security guide (Oct 2024) and Foundation Models report (2025); OpenSSF Sigstore model-signing v1.0 (Apr 2025); Microsoft, Lumma takedown (May 21, 2025) and Digital Defense Report 2025; Cisco Talos, exposed Ollama servers (Sept 2025); Anthropic, Sleeper Agents (Jan 2024); HiddenLayer, ShadowLogic (Oct 2024); CrowdStrike incident reports (July 2024); Executive Orders 14290 (May 1, 2025), 14319 (July 23, 2025) and the Dec 11, 2025 order on state AI laws; OMB memo of Dec 11, 2025; Rescissions Act of 2025 (H.R. 4); MedPAC March 2025 report; Stanford AI Index 2025; EU AI Act Article 53; EU Data Act (Reg. 2023/2854); EU Cyber Resilience Act; Penney, Berkeley Technology Law Journal (2016); Estonia X-Road statistics; Apertus model card and data recipes (Sept 2025; Aug 2026); The Register and The Decoder on Muse Spark (Apr 8, 2026).


# Part 2. Fit: who it serves, what it buys them, what it avoids

## 7. Demand: who the personal layer is for

| Population | Count | Source |
| --- | --- | --- |
| Students ages 3 to 21 served under IDEA | 7.5 million in 2022-23, 15% of public-school students (up from 6.4 million in 2012-13); 7.5 to 7.9 million in 2023-24 depending on the count (NCES vs. CRS); an advocacy analysis of 2024 data puts it at 8.2 million | NCES Condition of Education; CRS R44624 (Feb 13, 2026); K-12 Dive |
| IDEA category mix | Specific learning disability 32%; speech or language 19%; other health impairment, which includes ADHD, 15%; autism 13%. These four are about 79% of the population a learning-disability-tuned model would target | NCES, 2022-23 |
| Students with a Section 504 plan only | 1.6 million (2020-21); with IDEA, roughly 9.5 million school-age children with a disability plan | ED Office for Civil Rights |
| Children with ADHD | 7.1 million ever diagnosed (11.4%), 6.5 million currently, 2022; about 1 million more than 2016 | CDC, National Survey of Children's Health |
| Adults with ADHD | 15.5 million (6.0%), half diagnosed in adulthood; 71.5% of those on stimulants had trouble filling prescriptions | CDC MMWR, Oct 2024 |
| Children with dyslexia | Pooled prevalence 7.1% of primary-school children (meta-analysis, 2022); about 3.5 million (estimate). No federal count exists | PMC8870220 |
| Adults with chronic conditions | 76.4% (about 194 million) with at least one; 51.4% (about 130 million) with two or more, 2023 data | CDC, Preventing Chronic Disease, 2025 |
| Adults with any mental illness | 61.5 million (23.4%) in 2024, 52.1% of whom received any treatment; serious mental illness 14.6 million. The 2025 survey reports 54.6 million (20.6%) and 18.2 million with serious mental illness, but SAMHSA says question changes make the years not comparable | SAMHSA NSDUH, July 28, 2025 and July 27, 2026 |
| Adolescents 12 to 17 | 15.1% (3.7 million) with a major depressive episode in 2025; 2.6 million (10.1%) with serious thoughts of suicide in 2024 | SAMHSA |
| Adults with a disability | 1 in 4 (more than 70 million); cognitive disability the most common type, 13.9% of adults | CDC, 2022 |
| Mental-health provider shortage | 137.1 million people in 6,807 shortage areas as of Dec 31, 2025; 27.3% of need met; 6,800 practitioners short. 53% of psychologists had no openings for new patients (2024) | HRSA; American Psychological Association |

## 8. What is spent on these people now

| Benchmark | Figure | $3,000 is | Source |
| --- | --- | --- | --- |
| US health spending per person, 2024 | $15,474; Medicare $16,779 and Medicaid $11,050 per enrollee | 19% of per-capita health spending; 27% of Medicaid per enrollee | CMS National Health Expenditure Accounts |
| Mental-health and substance-use treatment | About $174 billion a year, roughly $520 per capita (2021-23) | 5.8 times current per-capita treatment spending | MEPS analysis, 2026 |
| Special education, per identified student | $13,127 in FY2020 (local $8,160, state $3,388, federal $1,578) in a 24-state sample; the last national study (1999-2000) found $12,525 vs. $6,556 for a general-education student | 23% of the per-pupil special-education cost | Bellwether (Oct 2024); AIR SEEP |
| Federal IDEA Part B | $14.2 to $14.6 billion a year, about $1,850 to $1,950 per child; a 10 to 13% share of excess cost against the 40% Congress authorized in 1975; never above about 19% | $3,000 × 7.9 million IDEA children = $23.7 billion, about 1.7 times the federal appropriation | CRS; CEC |
| School-based Medicaid | About $7.5 billion a year for nurses, counselors, speech pathologists and transport | | American Psychiatric Association, Feb 2025 |
| Medicaid long-term supports for intellectual and developmental disability | Home and community-based services up to $48,458 per person a year (2019); institutional care $145,306 (2020); $86.9 billion total in 2023 | | University of Minnesota RISP |
| The only prior per-head tech subsidy | Affordable Connectivity Program, $360 a year per household, 23 million households, ended May 31, 2024 | 8.3 times the ACP benefit | FCC |

## 9. What $3,000 buys in these domains (2025 to 2026 prices, estimates)

| Purchase | Price | Inside the $3,000 |
| --- | --- | --- |
| Device for 7 to 14 billion parameter models | Mac mini M4 with 16 to 24 GB, $599 list (sale $469 to $549) | $150 a year over four years |
| Device for 70 billion parameter models (128 GB memory) | $2,459 (Framework Desktop, early 2026) rising to $3,324 to $4,349 for 128 GB machines by Sept 30, 2026; Mac Studio 128 GB about $3,499 to $4,000; DGX Spark $3,999 list, $4,699 street (Aug 2026) | $615 to $1,090 a year over four years, depending on when it was bought |
| Electricity | 150 W at 8 hours a day, about $80 a year; continuous, about $239 | 3 to 8% |
| Tuning the model to one person | A 7B QLoRA run is $1.36 to $4.72 of rented compute (4 to 8 hours on one RTX 4090); a 70B run about $10 to $16; quarterly re-tuning $8 to $64 a year | under 2% |
| Storing the personal layer | An adapter of 80 to 160 MB per person on a 7B model; Apple's on-device adapters are tens of megabytes and swap in and out | negligible |
| Share of a public base model | Llama 3.1 405B took 30.8 million GPU-hours, about $62 million of compute; spread over 340 million people, 18 cents. A $1 billion open model: $2.94 a person | negligible |
| Licensed assistive software | Lexia $35 per student a year; Read&Write $170 to $184; Khanmigo $44; Proloquo2Go $250 one time; dedicated speech-generating devices $6,000 to $10,000 list, usually insurance-funded (price unverified) | |
| Human hours at market rates | Orton-Gillingham tutoring $113 an hour (26 hours); general tutoring $25 to $60 (50 to 120 hours); therapy $143 average self-pay (21 sessions); BetterHelp $260 to $400 a month (7.5 to 11.5 months); speech therapy $100 to $200 a session; ABA $120 to $150 an hour (about 20 hours, one to two weeks of a typical program) | |
| Monitoring | Dexcom Stelo over-the-counter glucose monitor $89 a month (about $1,068 a year); Bluetooth blood-pressure cuff $25 to $120; a fully billed year of remote patient monitoring at Medicare rates about $1,110 | |
| **The residual for human review** | **About $1,700 after a 128 GB rig and power; about $2,750 after a 7 to 14B machine.** That buys about 15 physician hours ($115 an hour), 60 counselor hours ($28.46), or 40 special-education-teacher hours (BLS May 2024 medians) | |

Three ways to spend the envelope for one adult with a chronic condition (estimates): human care only, 21 therapy sessions; monitoring, glucose monitor plus cuff plus remote monitoring, about $2,230, with $770 left for five sessions; local model, $200 of amortized hardware, $0 model license, the same devices at about $1,120, and about $1,680 for human hours.

## 10. What the models can do today, and where they fail

**Measured gains, all with a human in the loop.** The only randomized trial of a generative-AI therapy chatbot (Therabot, NEJM AI, March 27, 2025; 210 adults; clinicians monitoring conversations) reported depression symptoms down 51% and anxiety down 31% after four weeks. A 2026 meta-analysis of 39 randomized trials found small-to-moderate effects on depression (g = 0.31) and anxiety (0.28). A Harvard physics trial found AI-tutor gains of 0.73 to 1.3 standard deviations over an active-learning class; Tutor CoPilot raised mastery 4 points across 700 tutors; a human-supervised AI tutoring trial (Eedi) added 5.5 points on novel questions. Domain tuning works at the condition level: MedGemma 27B scores 87.7% on MedQA against 74.9% for its untuned base (July 2025).

**Where the local class is weaker.** The models that fit on a phone or a $599 machine score lower where it matters most: MedGemma 4B reaches 64.4% on MedQA; run on a laptop with compressed weights it scored 0.45 on HealthBench and met only 7.2% of the criteria for asking about missing context. A March 2026 preprint reports Llama 70B hallucinating in 19.7% of textbook-grounded medical answers (unverified). Six models elaborated on a planted false detail 50 to 82% of the time (Mount Sinai, Aug 2025). Sub-2-billion-parameter tutors produced fluent, confident, wrong arithmetic (2026).

**Where unguarded AI reduced learning.** Students given unguarded GPT access scored 17% lower on the unassisted exam (Bastani et al., PNAS, 2025); a 2026 university trial of 2,379 students reports lower final grades with an AI tutor offered (0.27 to 0.37 SD; the checkers could not locate the paper). Uptake was about 15% in that trial, and a Khanmigo study found students largely did not use the tool (Chalkbeat, Aug 25, 2026). Controlled evidence on generative AI for learning disabilities is thin: a 2025 review found 11 studies with 3,033 participants, generative AI in one 60-child study.

**Safety on a device the person controls.** Safety training was removed from Llama 3 8B in one to five minutes on one GPU for under $0.50, and from the 70B model in 30 to 45 minutes (Palisade, July 2024); under $200 of LoRA compute dropped Llama 2 70B refusals below 1% (Oct 2023). Of 63 small instruction-tuned models (100 million to 7 billion parameters), 47.6% averaged an attack-success rate above 0.4 across eight jailbreak methods, with no relation to size (March 2025). A local model receives no server-side fix when a crisis-response failure is found.

**Churn and labor.** Adapters are locked to their base model, and base models change every few months (Mistral 3, Dec 2025; Qwen3.5, Mar 2026; Gemma 4, Apr 2026); re-tuning a national fleet costs $0.5 to $0.8 billion per cycle for 7B models and $3.3 to $5.4 billion for 70B (estimate), unless adapter transfer or profile-to-adapter generation (NeurIPS 2024; Oct 2025) pans out. One review hour per person per year is 340 million hours, about 163,000 full-time clinicians or teachers; special-education teacher employment is projected to fall 1% by 2034; AI drafts did not shorten physician message time in a 52-physician trial (26 to 31 seconds).

**Who lacks the device.** Smartphone ownership is 82% among adults earning under $30,000 against 97% above $100,000, and 78% among adults over 65 (Pew, 2025).

## 11. Abuse comparison: what a local model avoids and what it does not

| Abuse on the open network | Figure | A local model |
| --- | --- | --- |
| Central vendor breaches of student and health data | PowerSchool: unauthorized access Dec 19 to 28, 2024; attacker claimed 62 million students and 9.5 million teachers, including SSNs and medical alerts; ransom paid; districts re-extorted May 2025. Illuminate: 10.1 million students, FTC order June 5, 2026. Instructure/Canvas: Apr to May 2026. ETS/California: about 7 million students including disability status, disclosed Oct 16, 2026. Change Healthcare: 192.7 million people. HHS OCR 2024: 663 large breaches, 242.9 million individuals. 55% of disclosed K-12 breaches since 2016 came through vendors | Avoids adding the person's AI data to these pools. Does not remove the school's or provider's own records |
| Ad-tech harvesting of health and mental-health data | GoodRx $1.5 million (Feb 2023); BetterHelp $7.8 million (Mar 2023); Cerebral $7 million (Apr 2024); jury verdict against Meta over Flo period-tracker data upheld Sept 16, 2025. Independently downloaded apps sit outside HIPAA; the FTC's Health Breach Notification Rule now covers them | Avoids, if the local app carries no ad SDK and sends no telemetry |
| School surveillance false flags | Gaggle: 1,200-plus alerts in ten months in one Kansas district, two-thirds judged non-issues, 200-plus from homework; a Florida girl jailed after an alert; GoGuardian monitors about 27 million students | Avoids when the family owns the device; not when the district manages it |
| Companion-chatbot dependency | 72% of US teens have used an AI companion, 52% regularly, 33% for social or emotional reasons (Common Sense, 2025); Character.AI settlements in four states, Jan 2026, including the death of 14-year-old Sewell Setzer and a Texas suit over an autistic 17-year-old; California SB 243 and New York's companion law in force | Partly avoids: no engagement-optimized server, no monetization loop. The behavior risk remains |
| Unsafe crisis responses | OpenAI (Oct 27, 2025): about 1.2 million users a week show explicit suicidal-planning indicators; RAND (Aug 2025): inconsistent handling of intermediate-risk questions across ChatGPT, Claude and Gemini; Stanford (June 2025): therapy bots listed tall bridges to a user signaling risk; an abliterated open model complied with 98% of harmful requests | Does not avoid. Cloud models get server-side fixes; a local model gets what the family installs |
| Financial fraud against the vulnerable | IC3 2025: $20.9 billion, 1,008,597 complaints; people 60 and over $7.75 billion; victims under 20, $67 million, up 198%. FTC 2025: $15.9 billion reported, investment scams $7.9 billion. People with cognitive disabilities are 41% more likely to experience multiple crimes and three times more likely to receive money-mule requests (UK) | Does not avoid; the channels are phone, text, social and crypto. Could be tuned to warn |
| Child sextortion and enticement | NCMEC 2025: 21.3 million CyberTipline reports; 1.4 million online-enticement reports, up 156%; 50,000-plus financial sextortion reports, 137 a day | Does not avoid |
| Safety stripping and jailbreaks | See section 10 | Easier locally: the person, or anyone with the device, holds the weights |
| Device loss, misconfiguration, vendor backups | Exposed, unauthenticated local model servers found on the public internet: 1,100-plus (Sept 2025) to 25,000-plus (Apr 2026); the VA's local-only PTSD Coach still backs up to the device's cloud account by default | Introduced or shifted: the person's full record concentrates on the least-defended device they own |
| Payment-side improper payments | Medicare fee-for-service $31.7 billion (7.66%) FY2024 and $28.8 billion (6.55%) FY2025; Medicare Advantage $19.1 billion and $23.7 billion; Medicaid $31.1 billion (5.09%). CMS notes improper payments are not synonymous with fraud | Constant, as the author set it: the same rates apply to either channel |

The health lens's tally of its six abuse classes: two substantially avoided, one partly avoided, three unaffected, one new concentration risk introduced.

## 12. SWOT, fit lenses

### Strengths

- **$3,000 is large next to what the federal government now puts behind each IDEA child** ($1,850 to $1,950) and covers the hardware floor many times over; a $599 machine runs 7 to 8B models and literacy licenses cost $35 to $184 a year.
- **The IEP is already an individualized, legally required specification**, the natural input for a per-student model; 57% of special-education teachers used AI for IEPs or 504 plans in 2024-25 (CDT survey).
- **Per-person tuning is cheap and the pieces exist.** A tuning run costs single-digit dollars; adapters are megabytes; Apple already ships per-feature adapters on a 3B on-device model; S-LoRA serves 2,000 adapters on one GPU.
- **A local-data-only design has a federal precedent in mental health.** The VA's PTSD Coach stores everything on the device and passed an independent privacy review (Mozilla).
- **On-device storage removes the breach pattern behind every FTC health-privacy action to date** (transmission of identifiable health data to advertisers) and the vendor breaches that account for 55% of disclosed K-12 incidents.
- **Demand is already there.** About 1 in 8 Americans aged 12 to 21 use chatbots for mental-health advice and 93% found it helpful (RAND, JAMA Network Open, Nov 2025); nearly 60% of teachers say AI improves accessibility for students with disabilities (Gallup/Walton, 2025).
- **Offline operation fits the homework gap.** About 12% of teens still cannot finish homework at times for lack of a computer or internet (2025).
- **Chronic-disease monitoring is the mature, cheap entry point.** 130 million adults with two or more conditions; FDA has cleared 1,200 to 1,500 AI-enabled devices, mostly monitoring and imaging; monitoring generates structured data a local model can read without a cloud.

### Weaknesses

- **The models that fit locally are the weakest class**, and the weakness is in noticing what is missing (7.2% context-seeking on HealthBench for the on-device medical model).
- **Unguarded AI has reduced learning in two large trials**, and the one positive therapy trial depended on humans watching every conversation.
- **Evidence specific to learning disabilities is tiny**: 11 studies, 3,033 participants, one 60-child generative-AI study, one 30-participant autism trial.
- **School hardware cannot run the model class the proposal needs**, so it implies a second device per child; district laptop prices rose from about $400 to over $600 by Aug 2026 on the memory shortage.
- **Safety moves to a device the family must maintain**, where it can be stripped for under $1 in minutes and receives no server-side fix.
- **$3,000 is small against the most expensive needs** in this population: ABA at 10 hours a week is about $62,400 a year; a neuropsychological evaluation $4,200 to $15,000; the full per-pupil special-education cost $13,127.
- **Engagement, not access, limits AI tutoring**: about 15% uptake when offered; human support is needed to sustain use (Stanford SCALE).
- **No generative-AI mental-health device has FDA authorization**; the agency's advisory committee (Nov 6, 2025) leaned toward trial-grade evidence plus post-market monitoring, which an offline model cannot report.
- **Human review time, not silicon, dominates the budget and is the scarce input**; 40 states plus DC project special-education teacher shortages.
- **The people most in scope are the least likely to own the device** (82% smartphone ownership under $30,000; 78% over 65).

### Opportunities

- **Condition-level tuning, then a small personal layer.** The largest measured gains come from condition data shared across millions (MedGemma +12.8 points on MedQA); a per-person adapter on top stays small (rank 8 in reproductions). One condition adapter serves millions; the per-person layer is megabytes.
- **The money already flows at a scale that makes $3,000 a reallocation.** Health spending is $15,474 per person; remote monitoring already has reimbursement codes worth about $1,110 a year.
- **Federal accessibility deadlines create demand for student-side tooling.** The ADA Title II web rule (WCAG 2.1 AA) applies from April 26, 2027 for large jurisdictions and April 26, 2028 for small ones.
- **Regulators are building a pathway, not only prohibiting.** FDA's advisory framework and its TEMPO real-world pilot; Utah's HB 452 (May 7, 2025) reads as a specification for a privacy-preserving mental-health chatbot that a local model satisfies by construction.
- **Large districts are pausing cloud chatbots but keeping supervised, narrow pilots open.** New York City barred student-facing generative AI through 8th grade for a year (Sept 2, 2026; about 600,000 students) while naming supervised high-school pilots.
- **The amended COPPA rule (compliance Apr 22, 2026) and the FTC's edtech orders favor architectures that collect less**; the Edmodo order (May 2023) held operators cannot push COPPA duties onto schools.
- **Offline AI tutors have shipped** (Intel and World Wide Technology, laptops for Guatemalan students, 2025); Apple pitched on-device models to schools at its 2026 Education Summit.
- **Unmet need is large enough that small effects at scale matter**: about 29.5 million adults with mental illness received no treatment in 2024.
- **Adapter transfer and generation could cut the re-tuning bill** when bases change (Trans-LoRA; profile-to-adapter hypernetworks).
- **A federal special-education expenditure study is underway**, results expected 2028, which would give the first national per-student cost baseline since 1999-2000.

### Threats

- **States are prohibiting AI from delivering therapy regardless of where it runs.** Nevada (June 2025); Illinois (Aug 2025): AI may not make therapeutic decisions or communicate directly with clients in therapy, fines up to $10,000 per violation. A model tuned to a person's emotional needs sits inside what is banned.
- **Companion-chatbot statutes attach liability to the operator, not the network.** California SB 243 (Jan 1, 2026): private right of action, up to $1,000 per violation; New York's law requires detecting suicidal ideation and directing users to crisis services, which an offline model cannot do.
- **Wrongful-death litigation has made chatbot conversations a litigable product harm.** Raine v. OpenAI (Aug 26, 2025); seven further suits in Nov 2025; the Character.AI settlements. The harm occurs in the conversation, not the transport layer.
- **Chatbot-associated psychosis is now a clinical case literature** in exactly the users the proposal targets; a validating, always-available, person-tuned model is the described risk profile (UCSF, 2025).
- **One device holding a person's complete health, education and emotional record is the highest-value target in their life**, and the people in scope are the most scam-vulnerable (adults over 60 lost $7.75 billion in 2025; 7,500 of them more than $100,000 each in 2024).
- **Policy backlash against student-facing AI is spreading from the largest district in the country**; only 26 states have K-12 AI guidance.
- **Federal special-education capacity is unstable.** Reduction-in-force notices hit 121 OSERS staff during the Oct 2025 shutdown; the reinstatement protection expired Jan 30, 2026. OSEP oversees about $15 billion.
- **Medicaid pressure threatens the $7.5 billion that pays for the human related services a local model would need to complement.**
- **Base-model churn multiplies the fleet re-tune bill**: $1.4 to $22 billion a year depending on cadence and model size (estimate).
- **Hardware inflation from the AI boom itself**: 128 GB machines roughly doubled in price between June and Sept 2026; a 340-million-unit buy at $3,449 is $1.17 trillion before any price response.
- **Clinical and teaching labor cannot scale with the fleet**: one review hour per person per year is about 163,000 full-time staff.

## 13. Figure-check ledger, part 2

| Lens | Figures re-checked | Confirmed | Corrected | Could not re-source in time |
| --- | --- | --- | --- | --- |
| Special education | 14 | 9 | 0 | 5 |
| Health and mental health | 8 | 6 | 2 | 0 |
| Technical economics | 8 | 4 | 2 | 2 |
| **Part 2 total** | **30** | **19** | **4** | **7** |
| **Both parts** | **89** | **51** | **15** | **23** |

Corrections applied above: IDEA counts given as a range (7.5 to 7.9 million for 2023-24; NCES vs. CRS) with the federal per-child figure as $1,850 to $1,950; the 2024-to-2025 mental-illness figures carry SAMHSA's non-comparability caveat; the HHS OCR count is 663 large breaches affecting about 242.9 million people, with Change Healthcare at about 192 million in the report to Congress and 192.7 million in the company's own filing; "outside HIPAA" narrowed to independently downloaded consumer apps; the jailbreak statistic restated as 47.6% of 63 instruction-tuned small models (100 million to 7 billion parameters) averaging an attack-success rate above 0.4 across eight methods; the 7B tuning run restated as $1.36 to $4.72 at the stated inputs. Not re-sourced and marked as such: the 2026 university AI-tutor trial, the Tobii Dynavox list price, the NCMEC 2025 counts, the Bellwether per-pupil split, the March 2026 Llama 70B hallucination preprint, and the late-2026 hardware prices.

## 14. Sources, part 2 (principal)

NCES, Condition of Education, Students With Disabilities (2022-23 and 2023-24); CRS R44624, IDEA primer (Feb 13, 2026); ED Office for Civil Rights, Civil Rights Data Collection 2020-21; CDC, National Survey of Children's Health 2022 (ADHD); CDC MMWR vol. 73 no. 40 (adult ADHD, Oct 2024); CDC, Preventing Chronic Disease 2025 (2023 BRFSS); CDC Disability and Health Data System 2022; SAMHSA, 2024 and 2025 NSDUH releases (July 28, 2025; July 27, 2026); HRSA, HPSA quarterly summary (Dec 31, 2025); APA Practitioner Pulse Surveys 2023 and 2024; CMS, National Health Expenditure Accounts 2024; MEPS mental-health spending analysis (2026); Bellwether, Who Pays for Special Education? (Oct 2024); AIR, Special Education Expenditure Project; CEC appropriations brief (2025); American Psychiatric Association letter on school-based Medicaid (Feb 17, 2025); University of Minnesota RISP; FCC and Senate statements on the ACP (2024); Heinz et al., Therabot RCT, NEJM AI (Mar 27, 2025); Sohn et al., npj Digital Medicine (2026); Bastani et al., PNAS (2025); Harvard physics AI-tutor RCT (2025); Tutor CoPilot (Stanford, 2024); Eedi and LearnLM trial; MedGemma technical report (arXiv 2507.05201, July 2025); Mount Sinai, Communications Medicine (Aug 2025); RAND, Psychiatric Services (Aug 2025); Stanford HAI therapy-chatbot evaluation (June 11, 2025); OpenAI, Strengthening ChatGPT responses in sensitive conversations (Oct 27, 2025); Palisade Research, Badllama 3 (July 2024); arXiv 2310.20624 (LoRA fine-tuning removes safety, Oct 2023); Zhang et al., arXiv 2503.06519 (small-model jailbreaks, Mar 2025); Trans-LoRA, NeurIPS 2024; OPPU (Feb 2024); S-LoRA (Nov 2023); Apple, Foundation Models updates (2024, 2025); BLS Occupational Outlook and OEWS (May 2024); Tai-Seale et al., JAMA Network Open (Apr 2024); EIA Short-Term Energy Outlook 2026; FDA Digital Health Advisory Committee (Nov 6, 2025); Utah HB 452 (2025); Illinois Wellness and Oversight for Psychological Resources Act (Aug 2025); Nevada AB 406 (2025); California SB 243 (Oct 13, 2025); New York AI companion law (Nov 5, 2025); Raine v. OpenAI complaint (Aug 26, 2025); Character.AI settlements (Jan 2026); Common Sense Media, Talk, Trust, and Trade-Offs (July 16, 2025); FTC orders: GoodRx (Feb 2023), BetterHelp (Mar 2023), Edmodo (May 2023), Cerebral (Apr 2024), Illuminate (June 5, 2026); FTC Health Breach Notification Rule (July 29, 2024); HHS OCR report to Congress for 2024; PowerSchool breach reporting and sentencing (2025); ETS/California breach disclosure (Oct 16, 2026); NCMEC 2025 data (2026); FBI IC3 2024 and 2025 reports; FTC Consumer Sentinel 2024 and 2025; NYC Department of Education generative-AI policy (Sept 2, 2026); DOJ ADA Title II web rule and interim final rule (Apr 20, 2026); Cisco Talos, exposed Ollama servers (Sept 2025); VA PTSD Coach documentation; Pew Research, Mobile Fact Sheet 2025.

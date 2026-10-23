# $3,000 a head: the purchasing-power case for personal, local models

SWOT, part 1 of 2. October 23, 2026. Findings only; no verdict.

**The proposal as set by the author.** Government spending power of $3,000 per citizen per year, about $1 trillion a year, creates demand for localized models: models that run on the person's own device, hold the person's data locally, and are tuned to that person's learning disability, health complications and emotional complexities. The purpose is fit for each person without exposure to an open network rampant with abuse. The payment channel (individual payments or large government payments) is not the deciding variable, because both carry fraud; fraud is treated here as a constant.

**How this was built.** Five independent analyst passes (fiscal, security and privacy architecture, policy feasibility, data dignity and civil liberties, red team), each required to source every point, followed by an adversarial re-check of each pass's load-bearing figures. Corrections from the re-check are applied below. Items the checkers could not re-source are marked (unverified). Part 2 adds the fit lenses: special education, health and mental health, and the technical economics of tuning a model to one person.

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

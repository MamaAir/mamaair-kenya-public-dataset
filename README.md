![MamaAir](assets/MamaAir.png)

MamaAir Climate-Contextual Maternal Health Dataset. Readme
This dataset provides high-fidelity, privacy-preserving synthetic JSON trajectories tracking 40-week maternal health journeys across climate-stressed Sub-Saharan Africa. This data pack was synthesized based on 100+ histories of pregnancy in the region of Big Nairobi (Kenya). It correlates daily physiological indicators with hourly climate and air quality anomalies (Gases, PM2.5, weather indices).
Optimized for fine-tuning, validating, and mitigating bioclimatic biases in medical LLMs and healthcare AI applications.

## Official Links

- [MamaAir AWS public dataset (v1)](http://mamaair-kenya-public-dataset.s3-website-eu-west-1.amazonaws.com/releases/v1/)
- [MamaAir application on GitHub](https://github.com/AirborneDiseaseRisksInstitute/mamaair)
- [MamaAir website](https://mamaair.africa)
 
Architecture (Data Mining & Processing Pipeline)
The end-to-end data mining pipeline transforms decentralized log events into structured longitudinal streams:
Ingestion Layer: Captures continuous daily logs from edge sensors (via the B2C mobile application): geo-positioning, tracking behavioural patterns, hydration metrics, symptomatology, and physical workload indicators.
Data Enrichment Layer: Automatically maps hourly ambient bioclimatic triggers (Gases, PM2.5 particulates, heat indices, humidity, and UV index) sourced from mix environmental model of OpenAQ, Copernicus Sentinel-5P satellite datasets and ground-level monitoring arrays.
Analytical Rules Engine: Dynamically calculates maternal-foetal health risks from environmental data, simulating indoor Household Air Pollution (HAP) exposure curves via domestic fuel, ventilation, and activity schedules. It programmatically generates daily risk-mitigation recommendations spanning four operational domains: diet, behaviour, activity, and mental well-being.
Serialization & Tokenization: Aggregates chronological daily logs into weekly gestational slices (weeks 1-40), dynamically mapping metrics against 11 foetal biological development systems.
Export (Machine-Readable Format): Generates the final streaming output in JSON (or JSON Lines) format. Each row represents a valid, independent trajectory object structured for seamless batch ingestion into distributed AI training frameworks.
 
2. Privacy (Anonymization Pipeline Sequence)
The data privacy protocol enforces zero-telemetry guarantees, mitigating linkage attacks and location reverse-engineering via Discrete Global Grid Systems (DGGS):
Edge Interception: Upon capturing a user's raw spatial tokens (Latitude/Longitude), the edge API instantly polyfills and converts them into an alphanumeric hexagonal spatial index using ‘Uber H3’.
GPS-to-H3 Index Conversion & Relational Lifecycle: Raw coordinates and timestamps are converted to an alphanumeric Uber H3 index, preventing disk logging or track tracing. Atmospheric datasets are joined strictly via this `h3_index` relational key. To enforce k-anonymity, the pipeline evaluates local density: high-density zones retain meso-resolution, while sparse sectors (k < 100) trigger blurring geometry shift.
Metadata Cleansing: All operational metadata has been completely stripped of medical facility markers, real names, and Personal Health Information (PHI/HIPAA compliant). The AWS Data Exchange sample records are 100% synthetic and safe for public distribution.

Core Use Case (Pharma)
Optimized for AI and pharma researchers to fine-tune foundational medical LLMs, mitigate geographic data starvation, and eliminate bioclimatic bias in Global South healthcare models.
Global pharma faces an efficacy paradox: why do prenatal micronutrient lines fail to deliver real-world clinical outcomes in climate-stressed markets?
Using MamaAir’s pregnancy longitudinal trajectories our RWE analytics bypassed "climate blindness" to uncover the root cause. When regional heat indices spike past 34°C and intersect with elevated household air pollution (PM2.5), maternal nausea severely amplifies. This physiological strain triggers a predictable 42% drop in Iron and Folic Acid compliance, as patients skip pills to avoid compounding gastric distress.
Actionable Value:
- R&D Innovation: Reformulating supplement lines with advanced enteric coatings optimized for high-heat, high-dehydration physiology.
- Digital Adherence: Pushing hyper-local, weather-triggered smart alerts to guide patient intake during localized environmental shocks.
MamaAir eliminates climate blindness, transforming complex geographic health risks into predictive commercial strategies.
 

MamaAir Climate-Contextual Maternal Health Dataset

Limitations and Allowed Use Specification

Document Identifier:limitations_and_allowed_use.mdlimitations_and_allowed_use.md

Dataset Reference:MamaAir Climate-Contextual Maternal Health Dataset (Kenya-First Synthetic Sample)MamaAir Climate-Contextual Maternal Health Dataset (Kenya-First Synthetic Sample)

Licensor:'MamaAir.Africa' (Kenya)'MamaAir.Africa' (Kenya)as a miner, owner and representative.as a miner, owner and representative.

1. Permitted and Allowed Use Cases

Subject to the Permissive Evaluation & Research Terms, this public synthetic data sample is explicitly authorized for the following operational workflows:

Download and Evaluation:Users are permitted to access, download, pipeline, and test the longitudinal JSON(L) and Parquet trajectories within any secure computing environment.Users are permitted to access, download, pipeline, and test the longitudinal JSON(L) and Parquet trajectories within any secure computing environment.

Research and Model Fine-Tuning:The data records are explicitly structured for academic, scientific, or commercial machine learning training, algorithmic validation, bias mitigation, and medical Large Language Model (LLM) fine-tuning.The data records are explicitly structured for academic, scientific, or commercial machine learning training, algorithmic validation, bias mitigation, and medical Large Language Model (LLM) fine-tuning.

Modification and Adaptation:Engineers can extract, transform, remap, or combine the fields (including the Uber H3 spatial index layers) to train and tune predictive real-world evidence (RWE) systems.Engineers can extract, transform, remap, or combine the fields (including the Uber H3 spatial index layers) to train and tune predictive real-world evidence (RWE) systems.

Dismantling Geographic Bias:This sample is intended for fine-tuning frontier models to bridge geographic data starvation, dismantle the clinical "Western/Global North Default" bias, and systematically reduce medical AI hallucinations across Sub-Saharan African healthcare applications.This sample is intended for fine-tuning frontier models to bridge geographic data starvation, dismantle the clinical "Western/Global North Default" bias, and systematically reduce medical AI hallucinations across Sub-Saharan African healthcare applications.

Targeted Institutional Validation:

For AI Developers:Validating model capabilities to achieve an anticipated +34% increase in clinical sensitivity for detecting heat-induced preeclampsia during early gestation and a 47% reduction in false negatives caused by applying rigid, climate-blind physiological thresholds.Validating model capabilities to achieve an anticipated +34% increase in clinical sensitivity for detecting heat-induced preeclampsia during early gestation and a 47% reduction in false negatives caused by applying rigid, climate-blind physiological thresholds.

For Pharmaceutical Companies:Evaluating real-world evidence (RWE) analytics to understand clinical trial translation failures and digital therapies, such as resolving iron-sufficiency misinterpretations to yield a 62% reduction in inappropriate prescriptions.Evaluating real-world evidence (RWE) analytics to understand clinical trial translation failures and digital therapies, such as resolving iron-sufficiency misinterpretations to yield a 62% reduction in inappropriate prescriptions.

For Local Services & Clinicians:Optimizing frontline community triage to achieve a predicted 40% reduction in false-positive emergency referrals by replacing static alert protocols with dynamic, climate-adjusted foetal baseline tracking.Optimizing frontline community triage to achieve a predicted 40% reduction in false-positive emergency referrals by replacing static alert protocols with dynamic, climate-adjusted foetal baseline tracking.

Redistribution:Sharing or republishing the dataset is permitted, provided that clear attribution is maintained as follows:Sharing or republishing the dataset is permitted, provided that clear attribution is maintained as follows:"Includes synthetic data tracking maternal-climate trajectories provided courtesy of the MamaAir via the AWS Data Exchange."

2. Core Clinical & Architectural Limitations

Users must strictly adhere to the following operational boundaries and boundaries of data representation:

100% Synthetic Nature:This dataset is entirely synthetic data generated programmatically via mathematical and probabilistic models based on regional climate indices and maternal health frameworks. It contains zero actual patient records, zero real-world identity tokens, and zero Protected Health Information (PHI).This dataset is entirely synthetic data generated programmatically via mathematical and probabilistic models based on regional climate indices and maternal health frameworks. It contains zero actual patient records, zero real-world identity tokens, and zero Protected Health Information (PHI).

No Medical Advice or Clinical Utility:This data product is delivered exclusively for mathematical evaluation, machine learning modelling, and AI engineering validation. Under no circumstances should this data be deployed for actual clinical diagnostics, real-time medical triage, or active obstetric intervention choices on real human patients.This data product is delivered exclusively for mathematical evaluation, machine learning modelling, and AI engineering validation. Under no circumstances should this data be deployed for actual clinical diagnostics, real-time medical triage, or active obstetric intervention choices on real human patients.

Mathematical Approximation:All simulated biological milestones, clinical symptoms, and atmospheric exposure curves are probabilistic mathematical representations and do not constitute professional clinical or medical advice, counseling, or diagnostic validation.All simulated biological milestones, clinical symptoms, and atmospheric exposure curves are probabilistic mathematical representations and do not constitute professional clinical or medical advice, counseling, or diagnostic validation.

3. Privacy, Anonymization & Grid Guardrails

To enforce zero-telemetry guarantees and mitigate linkage attacks or location reverse-engineering, the data structure is limited by specific spatial-temporal discretization sequences:

GPS Obstruction:Raw spatial coordinates (Latitude/Longitude) and exact granular timestamps are completely excluded and wiped from memory layers. No track tracing or medical facility markers are present.Raw spatial coordinates (Latitude/Longitude) and exact granular timestamps are completely excluded and wiped from memory layers. No track tracing or medical facility markers are present.

Spatial Discretization:Geographical positioning is restricted to alphanumeric hexagonal spatial indexes utilizing the Uber H3 format.Geographical positioning is restricted to alphanumeric hexagonal spatial indexes utilizing the Uber H3 format.

Geometry Blurring (k-Anonymity):Atmospheric and environmental layers are joined strictly via the H3 relational key. In sparse or rural sectors where local user density drops below k < 100, the pipeline triggers an automated parent-resolution function, permanently and irreversibly blurring the geometric grid resolution to a macro-zone boundary.Atmospheric and environmental layers are joined strictly via the H3 relational key. In sparse or rural sectors where local user density drops below k < 100, the pipeline triggers an automated parent-resolution function, permanently and irreversibly blurring the geometric grid resolution to a macro-zone boundary.

Regulatory Compliance:All operational metadata has been thoroughly cleansed, rendering the sample fully compliant with GDPR, HIPAA, and global PHI standards.All operational metadata has been thoroughly cleansed, rendering the sample fully compliant with GDPR, HIPAA, and global PHI standards.

4. Scope of the Synthesized Cohort

Localized Context:The baseline distributions, covariance matrices, and generative weights are programmatically derived from 100+ authentic maternal pregnancy histories collected within the urban and peri-urban regions of Big Nairobi, Kenya.The baseline distributions, covariance matrices, and generative weights are programmatically derived from 100+ authentic maternal pregnancy histories collected within the urban and peri-urban regions of Big Nairobi, Kenya.

Cohort Representation:The data lines simulate user group WQ1, which models over 55% of all maternal paths and pregnancy trajectories across climate-stressed, low-resource settings in Kenya.The data lines simulate user group WQ1, which models over 55% of all maternal paths and pregnancy trajectories across climate-stressed, low-resource settings in Kenya.

Temporal Resolution:Trajectories are restricted to independent 40-week (280-day) longitudinal gestational windows mapping sequentially against 11 distinct fetal biological development systems.Trajectories are restricted to independent 40-week (280-day) longitudinal gestational windows mapping sequentially against 11 distinct fetal biological development systems.

5. Technical Rules Engine & Dependency Constraints

The longitudinal variations within the dataset are tied to explicit algorithmic rules, as defined in the system documentation filesof MamaAir (with additional request):of MamaAir (with additional request):

Symptom-to-Risk Confounding:Symptoms are not randomized; they are strictly mapped to 10 specific health risks via a Level 2 Symptom Confirmation Layer. These include Preeclampsia (HDP), Preterm Birth, Gestational Diabetes (GDM), Placental Abruption, Anemia, PROM, Hyperemesis, CV Complications, Foetal Hypoxia (FH), and Low Birth Weight (LBW)/Fetal Growth Restriction (FGR).Symptoms are not randomized; they are strictly mapped to 10 specific health risks via a Level 2 Symptom Confirmation Layer. These include Preeclampsia (HDP), Preterm Birth, Gestational Diabetes (GDM), Placental Abruption, Anemia, PROM, Hyperemesis, CV Complications, Foetal Hypoxia (FH), and Low Birth Weight (LBW)/Fetal Growth Restriction (FGR).

Triage Class Stratification:Symptoms are restricted to a 4-Class physiological prioritization hierarchy: Class 1 (Acute & Emergency Indicators), Class 2 (Condition-Specific Systemic Indicators), Class 3 (Fetal Activity & Growth Markers), and Class 4 (Lifestyle & Environmental Stressors). Downstream models must evaluate clinical alerts relative to these strict classes.Symptoms are restricted to a 4-Class physiological prioritization hierarchy: Class 1 (Acute & Emergency Indicators), Class 2 (Condition-Specific Systemic Indicators), Class 3 (Fetal Activity & Growth Markers), and Class 4 (Lifestyle & Environmental Stressors). Downstream models must evaluate clinical alerts relative to these strict classes.

Bioclimatic Trigger Thresholds:Environmental exposure values drive non-linear risk accumulations based on precise climate triggers. These include extreme ambient heat waves (temperatures exceeding local 90th/95th percentiles or acute shocks >35°C) and solar UV-B radiation anomalies (extreme indices >8 or severe shortfalls <45 kJ/m²).Environmental exposure values drive non-linear risk accumulations based on precise climate triggers. These include extreme ambient heat waves (temperatures exceeding local 90th/95th percentiles or acute shocks >35°C) and solar UV-B radiation anomalies (extreme indices >8 or severe shortfalls <45 kJ/m²).

Behavioral-Physiological Dependencies:The data explicitly reflects real-world physiological friction points. For example, when regional heat indices spike past 34°C and intersect with high household air pollution (PM2.5), simulated maternal nausea severely amplifies. This directly triggers a predictable 42% drop in Iron and Folic Acid (IFA) supplement compliance as the synthetic entity skips pills to avoid compounding gastric distress. Machine learning frameworks evaluating this data must treat adherence drop-offs as an endogenous response to climate-induced physiological strain rather than random missingness.The data explicitly reflects real-world physiological friction points. For example, when regional heat indices spike past 34°C and intersect with high household air pollution (PM2.5), simulated maternal nausea severely amplifies. This directly triggers a predictable 42% drop in Iron and Folic Acid (IFA) supplement compliance as the synthetic entity skips pills to avoid compounding gastric distress. Machine learning frameworks evaluating this data must treat adherence drop-offs as an endogenous response to climate-induced physiological strain rather than random missingness.

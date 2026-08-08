MamaAir Climate-Contextual Maternal Health Dataset.Data Dictionary

Production-Grade Technical Documentation & Schema Specification(Kenya-First Cohort Sample "Amani WQ1")

Document Version:2.1.0

Data Format:JSON (Lines) Longitudinal Trajectories

Time Resolution:Daily Timeline (280 Days / 40 Gestational Weeks per Trajectory)

Licensing:Permissive Evaluation & Research Terms (MamaAir.Africa)

Target Platform:AWS Data Exchange & Registry of Open Data on AWS

1. Architectural Blueprint & Core Logic

The MamaAir dataset provides high-fidelity, privacy-preserving synthetic JSON records tracking full-term maternal health journeys across climate-stressed Sub-Saharan African urban environments (modelled on theWQ1 cohortrepresenting over 55% of maternal paths in Big Nairobi, Kenya).

1.1 The Inherited History of Reasoning

Traditional health datasets store isolated clinical encounters, creating a "blind spot" around lifestyle, climate and air pollution exposure. The MamaAir Digital Model Rules Engine remedies this by preserving an unbrokenhistory of reasoningacross 280 daily slices.

The underlying algorithm moves down a 4-level logic tree:

Level 0 (Core Data Inputs):Fuses static maternal profiles with daily microenvironmental anomalies (PM2.5), greenhouse gases, thermodynamic heat indices).

Level 1 (Risk Assessment Layer):Computes evidence-based Relative Risk (RR) multipliers against a baseline to produce continuous mathematical proxies. It models the cumulative degradation of maternal-fetal tolerances over multi-week windows.

Level 2 (Symptom Confirmation Layer):Validates risk flags against self-reported symptoms, categorizing them into physiological stress tiers.

Level 3 (Recommendation Engine):Activates clinical safety and mitigation vectors (Nutrition, Behaviour, Activity, and Midwifery Service routing).

1.2 Core Mathematical Formulation

Downstream AI models absorb temporal causality because risk states do not reset daily. Instead, they compound using theIntegrative Pregnancy Risk (IPR)non-linear aggregation formula:

Where:

r_iis the specific conditional risk factor triggered by lifestyle or environmental variables.

w_iis the clinical severity weight derived from obstetric frameworks. Emergency factors (e.g.,Placental Abruption= 2.0,Preeclampsia= 1.8) scale the index more aggressively than reversible factors (e.g.,Dehydration= 0.9,Oxidative Stress= 0.8).

2. Top-Level Schema Architecture

Each line in the dataset represents a single, complete 40-week pregnancy trajectory array. The top-level root object contains metadata block parameters alongside individual nested tracking matrices:

3. Detailed Data Layer Definitions

3.1 Base Identity Field

track_id (String)

Description:Unique synthetic sequential record identifier (e.g., "TRK_0001"). Completely decoupled from real patient databases.

3.2 Layer A:static_profile(Baseline Demographics & Socio-Economics)

Establishes the permanent conditioning parameters for the trajectory before daily climate exposure loops begin.

Field Name

Type

Value Range / Allowed Values

Technical Description & Analytical Context

age

Integer

15 to 45

Maternal age at the time of conception.

bmi

Float

16.0 to 38.5

Pre-pregnancy Body Mass Index. Standardized distribution across localized urban populations.

race

String

Black/African, Indian, Arabic

Coarsened to macro-demographic categorization to prevent localized ethnic tracking.

employment_category

String

Outdoor/Informal, Agricultural, Indoor/Informal-Retail, Indoor/Domestic, Unemployed

Broad occupational archetype used by the engine to condition physical workload and default exposure vectors.

work_description

String

e.g., "Roadside fried maize vendor", "Market trader", "Urban farming"

Synthetic free-text summary describing typical daily tasks and physical demands.

cooking_fuel

String

Biomass (Charcoal/Wood), Kerosene, LPG (Gas), Ethanol, Mixed

Primary domestic energy source. Acts as the baseline modifier for simulated Household Air Pollution (HAP).

ventilation

String

Open Eaves / No Chimney, Single Window, Multiple Windows, Mechanical Fan

Fixed structural parameters of the domestic cooking zone affecting microenvironmental PM2.5 retention.

water_distance_km

Float

0.0 to 5.5

Distance from the primary household to a clean water source; conditions baseline daily physical exertion.

detergent_use.type

String

Traditional Ash/Bar Soap, Commercial Powder, Mixed

Behavioral category for skin barrier integrity and chemical exposures.

detergent_use.frequency

String

Daily, 2-3 times/week, Weekly

Routine marker mapping chemical exposure density.

parity

Integer

0 to 8

Number of previous live births. Primes baseline physiological risk settings (e.g., 0 for primigravida).

climate_zone

String

Highland Tropical, Semi-Arid, Urban Heat Island, Peri-Urban

Macro-environmental context classification.

exposure_tier

String

High, Medium, Low

Calculated composite tier based on fuel type, work description, and transit environment.

3.3 Layer B & C:journey[](Daily Nested Longitudinal Resolution)

An array of exactly 280 sequential entries tracking the daily evolution of environmental, behavioral, and clinical markers.

Maternal Journey Structure

Field Name

Type

Value Range

Technical Description & Analytical Context

day

Integer

1 to 280

Continuous sequential loop timeline index.

gestational_week

Integer

1 to 40

Derived gestational week (per 7 days).

trimester

Integer

1, 2, 3

Gestational phase mapping (Days 1-84 = Trimester 1; 85-182 = Trimester 2; 183-280 = Trimester 3).

Environmental Exposure

Field Name

Type

Value Range / Units

Technical Description & Analytical Context

environment.pm25

Float

5.0 to 350.0 mu g/m3

Daily ambient fine particulate matter exposure. Fuses satellite API, OpenAQ, and localized ground arrays.

environment.no2

Float

0.0 to 120.0 ppb

Ambient Nitrogen Dioxide concentration; tracks proximity to vehicular transport corridors.

environment.heat

Float

16.0 to 44.0 °C

Daily maximum Heat Index combining ambient temperature with relative humidity.

environment.humidity

Float

10.0% to 100.0%

Ambient relative humidity percentage.

environment.uv_index

Float

0.0 to 16.0

Solar Ultraviolet radiation index. Multi-week cumulative shifts trigger cardiovascular and vascular baseline adjustments.

environment.climate_zone

String

Matches root configuration

Realized regional microclimate profile during the tracking day.

Nutrition & Hydration

Field Name

Type

Value Range / Units

Technical Description & Analytical Context

nutrition_hydration.water_l

Float / Null

0.5 to 5.0 Liters

Patient logged daily liquid intake. Set to null on days simulated as "unreported/missing."

nutrition_hydration.diet_consistency_score

Float / Null

1.0 to 10.0

Index of compliance with localized microelement recommendations.

nutrition_hydration.supplement_adherence

Float / Null

0.0 to 1.0

Logged daily compliance with Iron and Folic Acid (IFA) or Multiple Micronutrient Supplements (MMS).

nutrition_hydration.dehydration_risk_proxy

Float

0.00 to 1.00

Probabilistic proxy index. Dynamically climbs when environment.heat scales past 34°C while water_l stagnates.

Workload & Activity

Field Name

Type

Value Range / Units

Technical Description & Analytical Context

workload_activity.standing_hours

Float

0.0 to 14.0 Hours

Cumulative hours spent standing; feeds uterine vascular strain models.

workload_activity.heavy_load

Boolean

0 (False), 1 (True)

Flag for daily lifting or shifting of items > 15 kg (e.g., water basins, charcoal sacks).

workload_activity.rest_breaks

Integer / Null

0 to 8

Number of seated rest sessions (>10 minutes) taken during work cycles.

Household Conditions

Field Name

Type

Value Range / Units

Technical Description & Analytical Context

household_conditions.cooking_practice

String

Indoor, Outdoor Shaded, Open Air

Modifies localized household air pollution calculation curves.

household_conditions.ventilation_efficiency

Float

0.00 to 1.00

Dynamic score modeling how effectively domestic windows/eaves purge charcoal combustion soot.

household_conditions.indoor_smoke_exposure

Float

10.0 to 500.0 mu g/m3

Mathematically simulated indoor PM2.5micro-concentration during active cooking cycles.

household_conditions.water_proximity_km

Float / Null

Matches static baseline

Current day's physical distance required to fetch water.

Mobility Patterns

Field Name

Type

Value Range

Technical Description & Analytical Context

mobility_patterns.commute_type

String

Walking (Unpaved), Matatu (Minibus), Motorcycle (Boda), Static

Mode of transit used. Used to weight environmental dust, vibration strain, and direct emission inhalation.

mobility_patterns.mobility_score

Float

0.00 to 1.00

Aggregated spatial footprint score calculated using truncated Uber H3 Resolution 9 hex centroids.

Symptoms

Overview. The Symptoms layer maps patient telemetry into theSymptom Confirmation Layer (Level 2)of the Digital Model architecture. The system monitors10 targeted health risks(Preeclampsia/HDP, Preterm Birth, GDM, Placental Abruption, Gestational Anemia, PROM, Hyperemesis Gravidarum, Cardiovascular Complications, Foetal Hypoxia, and LBW/FGR) by grouping clinical indicators into a strict 4-Class physiological triage framework. This structures self-reportedsigns alongside environmental variables, transforming subjective logs into machine-learning ready biomarkers that trace how ambient heatwaves, dehydration, and biomass smoke exposure break down maternal-fetal tolerance curves.

The 4-Class Triage Concept.This physiological framework prioritizes data tracking by clinical severity and actionable window.Class 1 (Acute & Emergency)flags immediate, non-reversible maternal emergencies requiring instant clinical intervention.Class 2 (Condition-Specific Systemic)monitors organ-system distress vectors highly sensitive to climate shocks.Class 3 (Fetal Activity & Growth)captures real-time fetal well-being, movement deceleration, and physical resource restriction within the uterus.Class 4 (Environmental & Constitutional Fatigue)indexes baseline physiological stress, serving as early math proxies for chronic dehydration, oxidative strain, and iron depletion before severe pathology manifests.

Symptoms Specification Table

Field Name

Type

Value Range / Format

Technical Description & Analytical Context

Class 1: Acute & Emergency Indicators

journey.symptoms.vaginal_bleeding

Boolean

0 (False), 1 (True)

Critical marker for acute Placental Abruption or Preterm Labor; triggers instant service monitoring alarms.

journey.symptoms.severe_abdominal_pain

Boolean

0 (False), 1 (True)

Triggers on acute uterine tenderness or rigidity; indicative of severe mechanical or vascular placental distress.

journey.symptoms.leaking_fluid

Boolean

0 (False), 1 (True)

Direct signal of Premature Rupture of Membranes (PROM); marks amniotic sac barrier failure under high late-gestation thermal stress.

journey.symptoms.chest_pain_palpitations

Boolean

0 (False), 1 (True)

Signifies extreme acute cardiovascular (CV) strain or hemodynamic collapse under intense solar irradiance.

journey.symptoms.contraction_frequency_high

Boolean

0 (False), 1 (True)

Presence of contractions $>1$ in 10 minutes prior to term; immediate marker for active preterm birth labor cascade.

Class 2: Condition-Specific Systemic Indicators

journey.symptoms.bp_alert

String

"Normal", "Elevated", "Stage_1", "Stage_2"

Cardiovascular telemetry indicator tracking chronic or acute hypertensive disorders (Preeclampsia/HDP).

journey.symptoms.persistent_headache

Boolean

0 (False), 1 (True)

Severe, unallayed neurological indicator correlating with Preeclampsia-induced vasospasms.

journey.symptoms.blurred_vision

Boolean

0 (False), 1 (True)

Vision disturbances or blind spots caused by microvascular constriction in HDP pathways.

journey.symptoms.severe_swelling

Boolean

0 (False), 1 (True)

Rapid, pathologically visible fluid retention localized in the maternal face or hands.

journey.symptoms.severe_vomiting

Boolean

0 (False), 1 (True)

Hyperemesis flag ($>5$ episodes/day); correlates with high heat index spikes which drive a 42% drop in Iron/Folic Acid compliance.

journey.symptoms.metabolic_fluid_strain

String

"None", "Thirst_Only", "Urination_Only", "Combined_Distress"

Captures multi-systemic pancreatic fluid strain markers indicative of Gestational Diabetes Mellitus (GDM).

Class 3: Fetal Activity & Growth Markers

journey.symptoms.fetal_kick_deceleration

String

"Normal", "Reduced_Mild", "Severely_Reduced", "Prolonged_Stillness"

Indexes fetal kinetic response: Normal ($>10$ kicks/2h), Reduced (5-9/2h), Severe ($<5$/2h), Stillness ($>4$h continuous inactivity). Triggers on Fetal Hypoxia (FH).

journey[].symptoms.excessive_hiccups

Boolean

0 (False), 1 (True)

Identifies acute respiratory baseline distress ($>5$ continuous hiccups/day) linked to cord orblood-flow restrictions.

journey.symptoms.belly_growth_stagnation

Boolean

0 (False), 1 (True)

Longitudinal observation tracking structural growth restriction (FGR/LBW) over multi-week observational arcs.

journey.symptoms.low_maternal_weight_gain

Boolean

0 (False), 1 (True)

Tracking parameter flagging flatlined maternal weight curves ($<300$g/week) during Trimesters 2 and 3.

Class 4: Environmental & Constitutional Fatigue Markers

journey.symptoms.persistent_fatigue_weakness

Float

0.0 to 5.0

Continuous physical exhaustion scale mapping real-world progression of Gestational Anemia under daily workload strain.

journey.symptoms.pallor

Boolean

0 (False), 1 (True)

Physical tissue oxygenation indicator (conjunctiva/nails) pointing to systemic hemoglobin depletion.

journey.symptoms.shortness_of_breath

Boolean

0 (False), 1 (True)

Dyspnea on minimal physical exertion; indexes advanced maternal iron and volume depletion.

journey.symptoms.dizziness_lightheadedness

Boolean

0 (False), 1 (True)

Captures postural and orthostatic instability caused by chronic ambient heat-induced vascular pooling.

journey.symptoms.heat_strain_proxy

Float

0.00 to 1.00

Probabilistic proxy score mapping internal maternal thermoregulatory exhaustion during extreme equatorial climate waves.

Referral & Behavioral Signals

Field Name

Type

Value Range

Technical Description & Analytical Context

referral_signals.high_risk_flag

Boolean

0 (False), 1 (True)

Automated flag triggered when the multi-layered IPR algorithm passes safety parameters.

referral_signals.urgent_referral

Boolean

0 (False), 1 (True)

Activated when Class 1 metrics or > 2 intersecting Class 2 systemic symptoms are confirmed.

referral_signals.behavioral_adaptation

String

None, Resting, Increasing Fluids, Cross-Ventilation, Shifting Cooking Hours

Reflects the recommendation engine's active advice path chosen or logged by the synthetic entity.

Antenatal Care Entry

Field Name

Type

Value Range

Technical Description & Analytical Context

anc_visit

Boolean

0 (False), 1 (True)

Indicates whether a formal clinical antenatal care interaction occurred on this specific day.

3.4 Supplemental Object: derived_signals

Aggregated trajectory metrics that help AI models interpret referral thresholds and long-term diagnostic trends without scanning individual daily arrays.

Field Name

Type

Value Range

Technical Description & Analytical Context

final_risk

String

Low, Moderate, High, Critical

Categorical assignment summarizing the overall safety of the 40-week timeline.

risk_probability

Float

0.00 to 1.00

The terminal probability score computed by the non-linear Relative Risk matrix.

high_risk_days

Integer

0 to 280

Cumulative count of days where high_risk_flag was active.

urgent_referral_days

Integer

0 to 280

Cumulative count of days where an emergency triage alert was broadcast.

3.5 Supplemental Object: quality_flags

Simulates the data collection friction common in resource-poor environments, enabling robust machine learning evaluation under realistic data missingness scenarios.

Field Name

Type

Value Range

Technical Description & Analytical Context

completeness_index

Float

0.00 to 1.00

Ratio of completely populated logs to the 280-day trajectory ceiling.

synthetic_confidence

Float

0.00 to 1.00

Generative matrix score reflecting internal sequence fidelity and schema compliance validation.

missingness_matrix

String

Binary Bitmask (e.g., "00100")

Identifies which specific layers were subjected to random packet loss emulation before imputation.

3.6 Supplemental Object: birth_outcomes

Terminal endpoints that provide validation labels for machine learning networks evaluating the long-term impacts of prenatal environmental exposure.

Field Name

Type

Value Range / Format

Technical Description & Analytical Context

gestational_age_at_delivery_weeks

Float

24.0 to 42.0

Final duration of pregnancy. Captures preterm birth outcomes triggered by environmental shock waves.

birth_weight_grams

Integer

500 to 4500

Neonatal birth weight. Accurately simulatesLow Birth Weight (LBW)outcomes (e.g., 2150g) following prolonged exposure to biomass smoke.

delivery_outcome

String

Live Birth, Stillbirth, Neonatal Death

Primary delivery status indicator.

neonatal_complications

String / Null

None, Respiratory Distress (Surfactant Deficit), Sepsis, Asphyxia

Captures neonatal complications linked to maternal inflammation or restricted placental blood flow.

mode_of_delivery

String

Spontaneous Vaginal Delivery (SVD), Emergency Caesarean, Elective Caesarean

Method of birth.

maternal_outcomes

String

Normal / Recovered, Postpartum Hemorrhage, Severe Preeclampsia Outcome

Postpartum maternal health status classification.

3.7 Supplemental Object: anc_summary

Summarizes patient compliance with antenatal care relative to international global standards.

Field Name

Type

Value Range

Technical Description & Analytical Context

total_visits

Integer

0 to 12

Total number of antenatal care visits attended during the 280-day cycle.

total_help_demand

Integer

0 to 12

Total number request of help (mobile service) from health care provider during the 280-day cycle.

visit_days

Array of Int

e.g., [14, 82, 140, 210]

Explicit timeline tracker indexing the exact days visits occurred.

who_minimum_met

Boolean

0 (False), 1 (True)

Assesses if the patient met the traditional 4-visit minimum (by WHO guideline).

4. Privacy, Security & Compliance Guardrails

To meet AWS Data Exchange standards and global data privacy frameworks (including GDPR and HIPAA), the generation engine enforces strict structural boundaries:

Zero Personal Health Information (PHI):The dataset contains no real patient records, names, contact histories, or unique identification credentials.

Spatial Anonymization:Exact GPS coordinates, municipal facility names, and route history logs are completely excluded. Regional mobility tracking is restricted to coarsened Uber H3 grid cells or high-level categorical commute descriptions to make reverse engineering impossible.

Clinical Evaluation Limit:All health indicators, blood pressure alerts, and risk proxies are synthetic values designed for ML validation. They are mathematical approximations and do not constitute professional clinical advice or utility.


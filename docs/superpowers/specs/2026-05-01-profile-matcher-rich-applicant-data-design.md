# Profile Matcher And Rich Applicant Data Design

## Goal

Build UniPath's next phase around student retention: a Canadian admissions profile matcher that helps students understand where they stand, what similar applicants looked like, and what gaps they can work on before decisions arrive.

The data moat should shift from generic admissions stats to structured applicant profiles:

- grades
- courses and curriculum rigor
- school/program decisions
- extracurricular detail
- source quality and confidence
- nearest accepted/rejected profile comparisons

This keeps the project useful to students while also creating a stronger technical story around extraction, normalization, entity taxonomies, profile matching, and data quality.

## Current State

UniPath already has:

- `949` student rows in SQLite
- `508` Reddit-scraped rows
- `434` BC sheet rows
- `7` user-submitted rows
- canonical school/program normalization through `canadian_programs.json`
- CUDO aggregate data for official grade distributions
- program pages with grade distributions, EC breakdowns, historical trends, and "Where Do You Stand?"

The current bottleneck is not the absence of generic public stats. It is the lack of rich, structured, user-comparable applicant profiles. CUDO and other public sources can make program pages look populated, but they do not explain what admitted students actually did.

## Product Thesis

Students return when UniPath can answer a living question:

> Given my grades, courses, ECs, and target programs, where do I realistically stand and what should I improve next?

That requires storing richer applicant data than the current `Student` row can represent cleanly. The product should become a profile comparison system, not just a probability calculator or stats browser.

## Competitive Positioning

AdmitMe and similar products can compete on volume and polished stats. UniPath should compete on Canadian-specific profile depth:

- course requirements and rigor matter across provinces
- AP and IB context is relevant but inconsistently reported
- ECs are important for selective programs but rarely structured in public datasets
- Canadian universities publish less applicant-profile data than many US schools

UniPath's edge should be:

> show the concrete types of students who got in, not just their grade ranges.

## AdmitMe Data Boundary

AdmitMe should be used only for competitive analysis, not as a scraped data source.

Their public terms prohibit copying materials and automated data collection without permission. Scraping their rich applicant pages would create legal, ethical, and portfolio-risk problems. It would also weaken the project's story because the core dataset would depend on a competitor's proprietary collection.

Allowed uses:

- study their public UX and field choices manually
- compare visible product positioning
- note feature gaps in UniPath's own roadmap

Disallowed for this project:

- automated scraping of AdmitMe profiles
- copying their applicant records into UniPath
- presenting their data as UniPath data

## Rich Applicant Profile Model

Add a profile layer that can be derived from existing `students` rows, Reddit posts, and future user submissions.

### ApplicantProfile

Fields:

- `id`
- `source_student_id`
- `source`
- `source_url`
- `source_confidence`
- `school_normalized`
- `program_normalized`
- `program_category`
- `admission_year`
- `decision`
- `decision_confidence`
- `province`
- `citizenship`
- `grade_average`
- `grade_context`
- `grade_confidence`
- `curriculum_type`
- `course_rigor_score`
- `profile_completeness_score`
- `created_at`
- `updated_at`

`grade_context` values:

- `TOP_6`
- `CORE_AVERAGE`
- `GRADE_12_AVERAGE`
- `GRADE_11_AVERAGE`
- `IB_PERCENT_CONVERTED`
- `UNKNOWN_PERCENT`

`curriculum_type` values:

- `REGULAR`
- `AP`
- `IB`
- `HONORS`
- `MIXED`
- `UNKNOWN`

### ApplicantCourse

Fields:

- `profile_id`
- `course_name`
- `course_subject`
- `course_level`
- `grade`
- `is_required_for_program`
- `source_confidence`

`course_level` values:

- `REGULAR`
- `AP`
- `IB_HL`
- `IB_SL`
- `HONORS`
- `DUAL_ENROLLMENT`
- `UNKNOWN`

Course data will be sparse in Reddit posts. The system should extract it opportunistically from Reddit but treat user submissions as the main source of reliable course detail.

### ApplicantActivity

Fields:

- `profile_id`
- `category`
- `activity_type`
- `raw_text`
- `role_level`
- `duration_months`
- `achievement_level`
- `program_relevance`
- `source_confidence`

`category` values:

- `LEADERSHIP`
- `BUSINESS`
- `STEM`
- `SPORTS`
- `ARTS`
- `VOLUNTEERING`
- `WORK`
- `RESEARCH`
- `COMPETITION`
- `ENTREPRENEURSHIP`
- `COMMUNITY`
- `OTHER`

`activity_type` should capture concrete student-recognizable entities:

- `DECA`
- `STUDENT_COUNCIL`
- `BUSINESS_CLUB`
- `HACKATHON`
- `ROBOTICS`
- `SCIENCE_FAIR`
- `HOSA`
- `DEBATE`
- `MODEL_UN`
- `VARSITY_SPORT`
- `TUTORING`
- `PAID_WORK`
- `RESEARCH_INTERNSHIP`
- `NONPROFIT`
- `PERSONAL_PROJECT`
- `OTHER`

`role_level` values:

- `MEMBER`
- `EXECUTIVE`
- `PRESIDENT`
- `FOUNDER`
- `CAPTAIN`
- `LEAD`
- `AWARD_WINNER`
- `UNKNOWN`

`achievement_level` values:

- `SCHOOL`
- `LOCAL`
- `REGIONAL`
- `PROVINCIAL`
- `NATIONAL`
- `INTERNATIONAL`
- `NONE`
- `UNKNOWN`

`program_relevance` values:

- `HIGH`
- `MEDIUM`
- `LOW`
- `UNKNOWN`

## Extraction Strategy

Use a two-pass extraction model.

### Pass 1: Existing Admissions Extraction

Keep the current Reddit extraction focused on:

- school
- program
- decision
- grade
- province
- citizenship
- raw EC text

This pass determines whether a post is a usable admissions outcome.

### Pass 2: Profile Enrichment Extraction

Run a second structured extractor over rows that have usable raw profile text.

Extract:

- curriculum type
- mentioned courses
- AP/IB indicators
- activity objects
- achievements
- role levels
- duration signals
- program relevance
- extraction confidence

This pass should be schema-validated and should not mutate the original `students` row. It creates or updates profile-layer records.

## Confidence Scoring

Every profile should carry confidence metadata so the frontend can avoid overclaiming.

Profile confidence should combine:

- source type
- school/program normalization confidence
- decision extraction confidence
- grade confidence
- EC detail confidence
- course detail confidence
- profile completeness

Suggested source weights:

- `USER_SUBMITTED`: high if validated form fields are complete
- `BC` / `BC_2025`: medium-high for grade/decision, low for rich EC/course detail unless present
- `REDDIT_SCRAPED`: variable; depends on extraction confidence and raw text detail
- `CUDO_OFFICIAL`: official aggregate only, not individual profile data

The UI should distinguish:

- `official aggregate`
- `community grade profile`
- `community EC profile`
- `course-rich profile`
- `low-confidence extracted profile`

## Matching Experience

The core retention feature is a profile matcher.

Student inputs:

- target school
- target program
- current grade average
- province/curriculum
- courses taken or planned
- EC list
- optional decision/outcome later

Output:

- closest accepted profiles
- closest rejected/waitlisted profiles when available
- grade percentile among known profiles
- course rigor comparison
- EC archetype comparison
- missing or weak profile signals
- confidence warning when the comparison set is thin

This should be framed as comparison and preparation, not deterministic admissions prediction.

## Similarity Algorithm

Start with an interpretable weighted similarity score.

Suggested weights:

- school/program match: required filter where possible
- grade distance: high weight
- curriculum/course rigor: medium weight
- required-course coverage: high weight for direct-entry programs
- activity category overlap: medium weight
- concrete activity type overlap: medium weight
- role/achievement strength: medium weight
- province/citizenship context: low-medium weight

The algorithm should return both:

- nearest profiles
- explanation of why they matched

Example explanation:

> Similar because both profiles target UBC Commerce, have 92-94 averages, include DECA/business leadership, and show sustained volunteering. Different because admitted profiles more often had executive or founder roles.

This interpretability matters more than model sophistication in v1.

## Applicant Archetypes

Build program-level archetypes from accepted profiles with sufficient EC detail.

Examples:

- `High-grade academic competitor`
- `Business leadership profile`
- `STEM competition builder`
- `Athlete plus community service`
- `Research-heavy science applicant`
- `Founder/entrepreneur profile`

Archetypes should be derived from structured activities and grades, not hard-coded descriptions.

Initial implementation can use rules and clustering-lite summaries:

- bucket profiles by dominant activity category
- separate high-achievement profiles from general participation
- compute median grade and common concrete activities per archetype
- hide archetypes below a minimum support threshold

## Data Collection Loop

User submissions need a value exchange.

Instead of asking users only to "submit your outcome," UniPath should let them create a profile before admission decisions and then update it later.

Flow:

1. User enters target programs and current profile.
2. UniPath returns nearest profiles and gaps.
3. User can save a local profile or anonymous profile token.
4. User returns after grade updates, course changes, EC additions, or decisions.
5. After admission season, UniPath asks for outcome updates.

This converts retention into data growth.

For v1, account creation can remain out of scope. A local saved profile or anonymous profile token is enough.

## API Surface

Add endpoints behind the FastAPI sidecar.

### `POST /profile-match`

Input:

- school
- program
- grade average
- province
- curriculum type
- courses
- activities

Output:

- matched accepted profiles
- matched rejected/waitlisted profiles
- similarity explanations
- grade percentile
- EC comparison
- course comparison
- data confidence

### `GET /programs/{school}/{program}/archetypes`

Output:

- archetypes
- support count
- median grade
- common activity types
- common role levels
- confidence label

### `POST /profiles`

Input:

- anonymous applicant profile
- optional outcome if known

Output:

- profile id or anonymous token
- normalized school/program
- extracted structured activities
- validation warnings

## Frontend Scope

Do not do a full frontend redesign yet.

Add only the screens needed to validate retention:

- profile entry form
- nearest profile results
- gap comparison panel
- program archetype section on detail pages
- update outcome prompt

Avoid presenting this as a precise probability engine. The user-facing language should emphasize:

- "similar profiles"
- "common admitted patterns"
- "where your profile is strong"
- "where your profile is thinner than similar admitted profiles"

## Privacy And Safety

Applicant profiles can become sensitive even when anonymous.

Rules:

- never show raw Reddit usernames
- do not store direct personal identifiers in v1
- avoid showing exact rare combinations that could identify a student
- aggregate or redact profiles when support is too low
- let user-submitted profiles be anonymous
- avoid deterministic claims like "you will get in"

Profile cards should be paraphrased and normalized, not raw copied text.

## Testing Strategy

Add tests for:

- profile schema validation
- activity taxonomy normalization
- course level normalization
- AP/IB extraction examples
- DECA/student council/hackathon/robotics extraction examples
- confidence scoring rules
- profile similarity ranking
- explanation generation
- archetype minimum support thresholds
- API response shape
- privacy redaction for low-support profile cards

## Phased Build

### Phase 1: Data Schema And Enrichment

- add profile tables
- add activity/course taxonomies
- write enrichment extractor
- backfill enriched profiles from existing rows
- measure profile completeness by source and program

### Phase 2: Matching Engine

- implement weighted similarity
- generate explanation strings
- add confidence labels
- expose `POST /profile-match`
- test on flagship programs

### Phase 3: Retention Loop

- build profile input flow
- show nearest profiles and gaps
- add anonymous saved profile token
- add decision update flow

### Phase 4: Program Archetypes

- compute archetypes for data-dense programs
- add archetypes to program detail pages
- hide low-support archetypes

## Flagship Programs

Focus first on programs where current data is strongest or user demand is high:

- UBC Vancouver Science
- UBC Vancouver Engineering
- UBC Vancouver Commerce
- University of Waterloo Computer Science
- University of Waterloo Engineering
- Western University Business Administration

The goal is depth on a few programs before broad but thin coverage.

## Out Of Scope

- scraping AdmitMe profile data
- building a full account system
- replacing the current program pages
- adding a black-box ML model for admissions prediction
- expanding CUDO coverage as the main differentiator
- making probability percentages the primary user experience

## Success Criteria

- Existing student rows can be enriched into structured profiles without losing original data.
- At least three flagship programs have meaningful accepted-profile comparisons.
- The profile matcher returns interpretable nearest profiles and gap explanations.
- Course and EC fields support both broad categories and concrete activity types.
- User-submitted profiles provide immediate value before a decision is known.
- The app can explain data confidence clearly instead of hiding thin or biased data.

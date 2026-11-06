For releases such as IRS-65265, the team reviews each requirement and manually assembles the ADF bundle, which can take about two weeks. Engineers must locate and package the correct scripts, configurations, reference assets, parameters, metadata, and version dependencies. They then verify that the bundle represents every ticket requirement and is compatible with the target Genexus software.

Sanity testing takes approximately another week. The team imports the bundle, exercises the applicable workflows, checks expected behavior, reviews logs and outputs, and documents results against the ticket requirements. When a test fails, engineers must determine whether the cause is the ADF, software, configuration, dependency, test environment, or an existing defect. Resolving these issues often requires repeated bundle revisions, reruns, and coordination among assay, validation, and software teams.

The process is repetitive but high-risk. Simple scripting can automate file movement, but it cannot easily interpret natural-language requirements or relate failures across release artifacts and logs. The result is a roughly three-week path to a validated candidate bundle, with late discovery of missing requirements or software conflicts creating additional delay.

### Source ticket

- Ticket: [IRS-65265](https://lsg-thermofisher.atlassian.net/browse/IRS-65265)
- Purpose: ADF #3 (v0.0.3) release requirements and validation scope
- Jira access: Internal/authenticated
- Details captured from: Ticket description, acceptance criteria, comments, and linked artifacts

# Manual Baseline: [Release/Ticket ID]

# Manual Baseline: ADF #3 (v0.0.3)

## 1. Release information

- Release/ticket: ADF #3
- Release type: ADF release
- Version: v0.0.3
- Start date: 09/07/26
- End date: 10/27/26
- Total elapsed calendar time: 37 days
- Is this data sanitized or representative?: [confirm]

## 2. Bundle preparation

- Finalize requirements: 09/07/26–09/08/26, 2 days
- Review and evaluate: 09/09/26–09/15/26, 1 week
- Bundle: 09/16/26–09/29/26, 2 weeks
- Total bundle-related elapsed time: approximately 23 calendar days
- Hands-on engineer time: Unknown
- Number of engineers involved: Unknown
- Number of bundle revisions: Unknown

## 3. Sanity testing

- Sanity Testing: 09/30/26–10/06/26, 1 week
- Mol Bio Runs: begins 10/07/26
- Analyze data: 10/21/26–10/27/26, 1 week
- Total release validation period: approximately 28 calendar days
- Number of test cases: Unknown
- Number of reruns: Unknown
- Hands-on test time: Unknown


## 1. Release information

- Release/ticket:
- Release type:
- Target Genexus/software version:
- Approximate release date:
- Is this data sanitized or representative?:

## 2. Bundle preparation

- Total elapsed time:
- Approximate hands-on engineer time:
- Number of engineers involved:
- Main steps performed manually:
  1.
  2.
  3.
- Approximate number of bundle revisions:
- Approximate number of file/configuration changes:

## 3. Bundle contents
### Bundle contents and changes

#### Configuration and reference files

- Updated Manticore SVB file
- Six module INI files:
  - TmapExecutionActor
  - VariantCallerActor
  - RNACountsActor
  - CnvActor
  - MSIActor
  - AnnotatorActor
- AnalysisArgs JSON file
- Updated DNA panel BED file
- Updated hotspot BED file
- New CNV baseline H5 file
- New CNV input-parameter JSON file
- New MSI baseline H5 file
- OVAT ruleset reused from ADF v0.0.2
- VNS 2.2.2 reused from Gx7.0.2

#### Binaries and scripts

- Updated Tmap binary
- CNV scripts
- Instrument workflow script containing the latest piercing script
- Updated MSI_IR binary
- Updated MSI baseline

### Part-number updates

The following part numbers must be updated for ADF #3 (v0.0.3). The values
currently shown in the existing ADF are being replaced with the v0.0.3
values. Some DNA values are temporary placeholders until the Manticore panel
is manufactured.

#### Manticore DNA and Fusion ADF

| Component | Existing/current value | v0.0.3 value | Status |
|---|---|---|---|
| DNA Panel Kit | `A47017` | `A40014056` | Temporary placeholder; replace when the Manticore panel is manufactured |
| RNA Panel Kit | `A47019` | `A47019` | Correct; Manticore uses the OCAPlus RNA/Fusion panel |
| DNA Primer Tube Pool 1 | `100093900` | `100200225` | Temporary OCAPlus placeholder |
| DNA Primer Tube Pool 2 | `100093901` | `100200226` | Temporary OCAPlus placeholder |
| RNA Primer Tube Pool 1 | `100093902` | `100093902` | Correct for the OCAPlus Fusion panel |
| RNA Primer Tube Pool 2 | `100093903` | `100093903` | Correct for the OCAPlus Fusion panel |

#### Manticore DNA-only ADF

| Component | Existing/current value | v0.0.3 value | Status |
|---|---|---|---|
| DNA Panel Kit | `A47017` | `A40014056` | Temporary placeholder; replace when the Manticore panel is manufactured |
| DNA Primer Tube Pool 1 | `100093900` | `100200225` | Temporary OCAPlus placeholder |
| DNA Primer Tube Pool 2 | `100093901` | `100200226` | Temporary OCAPlus placeholder |

### Source repositories

- ADF DNA and Fusion repository:
  [csd-adf-gx-manticore-v2-dnafus-70](https://github.com/thermofisher/csd-adf-gx-manticore-v2-dnafus-70/)
- ADF DNA-only repository:
  [csd-adf-gx-manticore-v2-dna-70](https://github.com/thermofisher/csd-adf-gx-manticore-v2-dna-70/)
- Configuration repository:
  [csd-motorcore-config-files/Manticore](https://github.com/thermofisher/csd-motorcore-config-files/tree/main/Manticore)

## 4. Requirements

- Number of ticket requirements:
- How were requirements tracked?:
- Were requirements mapped to bundle components?:
- Were any requirements missed or clarified late?:
- If yes, describe one example:
- tickets: 
- IRS-62690
- IRS-64099
- IRS-66170
- IRS-65459

- IRS-65820
- IRS-65922
- IRS-65923
- IRS-66003
- IRS-66228
- IRS-66455
- IRS-66464
- IRS-66745

- IRS-59604
- IRS-58898

## 5. Dependencies and validation

- Software versions checked:
- External/internal dependencies:
- How were dependencies checked?:
- Did you encounter missing or incompatible dependencies?:
- If yes, describe one example:

## 6. Sanity testing

- Total elapsed test time:
- Approximate hands-on test time:
- Number of test cases:
- Types of tests performed:
- Which tests were automated?:
- Which tests were manual?:
- How were expected results determined?:
- How many test reruns were needed?:

## 7. Failures and triage

- Number of failed tests:
- Failure categories:
  - ADF defect:
  - Software defect:
  - Configuration problem:
  - Dependency/version problem:
  - Test-environment problem:
  - Existing known defect:
  - Other:
- Typical time to identify the likely cause:
- Typical people/teams involved:
- How were failures documented?:
- Was a bug report created?:

## 8. Evidence and approval

- What evidence was produced?:
- Where was evidence stored?:
- Who reviewed the results?:
- What approval was required?:
- What information was missing or difficult to reproduce?:

## 9. Overall baseline

- Total time from ticket to validated candidate:
- Estimated manual effort:
- Biggest source of delay:
- Biggest source of rework:
- Biggest risk:
- What would have saved the most time?:
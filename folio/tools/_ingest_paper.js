/* 本次入库用的原文正文 —— 全部逐字取自 Cardiovascular Research 原文，
   未做任何改写。quote 能否锚定，取决于这里的文本与原文是否逐字一致。 */
module.exports = `# Mass spectrometric proteome profiling using a deep spectral library reveals homogenization of right and left atrial proteomes in persistent atrial fibrillation patients

## Abstract

### Aims

Pulmonary veins in the left atrium (LA) are well-established as a critical site for the initiation of atrial fibrillation (AF). Emerging evidence suggests that in persistent AF (persAF), AF triggers may extend beyond LA. However, the extent to which AF-associated remodelling involves the right atrium (RA) in persAF remains a subject of debate. To address this, we employed a proteomic approach aiming at investigating AF-associated remodelling in the RA relative to the LA in persAF.

### Methods and results

RA and LA samples were obtained from sinus rhythm (SR) patients, patients with persAF undergoing open-heart surgery, and non-failing donor hearts rejected for transplantation. A reference spectral library representing the human cardiac proteome was employed to assess the RA and LA proteomes by data-independent acquisition mass spectrometry. Protein levels were quantified by immunoblotting of human atrial tissue. Plasma levels of NT-proANP and NT-proBNP were measured in SR and persAF patients. Fibrosis levels were quantified in paraffin-embedded sections using Masson-Goldner trichrome staining. A spectral library representing 13 539 human proteins was generated from five anatomical regions of five independent donor hearts. In persAF RA, we observed marked myolysis, excessive extracellular matrix deposition and a prominent similarity to the failing ventricular proteome, all comparable to persAF LA. Although significant proteomic differences were observed between the RA and LA from SR patients, a comparison of RA and LA proteomes in persAF patients revealed proteome homogenization between the two atrial chambers. RA contributes to this homogenization by losing RA-specific markers, while gaining LA-specific markers.

### Conclusion

Our findings suggest that RA undergoes comparable AF-associated remodelling to LA, contributing to atrial proteome unification which represents a hallmark of persAF.

## 1. Introduction

Atrial fibrillation (AF) is the most common cardiac arrhythmia associated with increased mortality and morbidity. Against the background of an aging population, the incidence of AF will further increase and will create a substantial socio-economic burden. Despite tremendous efforts in identifying underlying mechanisms during the last years, there is a lack of effective therapeutic strategies, particularly for patients with long-term persistent AF (persAF).

AF is a chronic progressive disease. Patients often initially show paroxysmal AF (pAF), consisting of self-terminating episodes lasting ≤ 7 days, then persistent and finally long-lasting persistent states that fail to self-terminate. The progressive nature of AF is thought to result from atrial remodelling leading to structural, electrophysiological, Ca2+-handling, and metabolic abnormalities that facilitate the initiation and maintenance of the arrhythmia.

In pAF, high-frequency re-entrant sources (rotors) in the left atria (LA) and pulmonary veins (PV) play an important role in the initiation and maintenance of the arrhythmia. These dominant high-frequency sources in the LA create left-to-right atrial frequency gradients that were previously shown in sheep model and in patients with pAF. Accordingly, ablation of LA dominant frequency sites and PV has been shown to terminate pAF, supporting the notion that LA sites 'drive' AF.

However, LA-to-right atrium (RA)-dominant frequency gradients are clearer in patients with pAF than those with persAF, where the efficacy of PV ablation is significantly reduced. This diminished effectiveness may be attributed to the increased AF-associated remodelling in persAF, which stabilizes re-entrant circuits. Despite this, strategies targeting atrial remodelling have so far been unsuccessful in maintaining sinus rhythm (SR). In addition, it has been suggested that there may also be high-frequency sources in the RA, which may promote AF maintenance in persAF, indicating a more prominent role of the RA in AF progression.

In SR there is a clear difference in gene expression and ion channel profile between right and left atria. Transcription factor paired-like homeodomain 2 (PITX2) has been suggested to play a significant role in the left-right asymmetry by modulating gene expression, ensuring the proper development and functional differentiation of the LA. Despite these apparent differences and the importance of RA in AF pathophysiology, it is largely unknown whether AF-associated remodelling is different between the RA and LA.

Here, we established a proteomic library of the human cardiac proteome in order to assess the RA and LA proteomes by data-independent acquisition mass spectrometry (DIA-MS), aiming to identify distinct protein abundance patterns and molecular markers that contribute to the functional and structural differences between the atria.

## 2. Methods

### 2.1 Study population

This study was approved by the George Washington University Institutional Review Board and the ethics committee of Goettingen University (No. 4/11/18) and conducted following the Declaration of Helsinki.

Of the 8 deidentified, explanted non-failing human hearts from deceased donors that were rejected for transplantation and included in this study, 5 were used for spectral library generation.

RA samples were obtained during open-heart surgery from 15 SR patients and 16 patients in long-standing persistent AF who were in AF during tissue sampling.

In 6 patients with persAF, paired LA samples were available and were used for intra-patient RA vs. LA comparisons.

For the corresponding control comparisons, RA and LA samples from the 8 aforementioned non-failing donor hearts were employed.

Immunoblot experiments comparing RA-SR vs. RA-persAF were carried out in an independent patient cohort comprising 28 and 24 patients with SR and persAF, respectively.

Histology experiments comparing RA-SR vs. RA-persAF and LA-persAF were carried out in an independent patient cohort comprising 13 and 6 patients with SR and persAF, respectively.

### 2.2 Sample collection

All hearts were explanted by a cardiothoracic surgeon and rapidly transferred to a research team member in the operating room. Coronary artery perfusion with ice-cold cardioplegic solution was used to arrest hearts. Hearts were then packed in a cooler with a cold cardioplegic solution to transport to the laboratory, with a total time from heart excision to laboratory of ∼20 min. Samples for proteomic analysis were dissected in a cardioplegic solution and snap-frozen in liquid nitrogen.

Each surgery patient gave a written informed consent. Excised appendages were snap-frozen in liquid nitrogen for biochemical, histological and mass spectrometry (MS) studies.

### 2.3 Proteome profiling: tissue lysis and protein digestion

All tissue samples were run on the same LC-MS instrument using the same chromatography separation method. Tissue samples were mixed with 30 uL lysis buffer (8 M urea in 100 mM aqueous NH4HCO3 with pH 8.0), a complete protease inhibitor cocktail and PhosSTOP phosphatase inhibitor cocktail in PCT microtubes, followed by 1 min centrifugation at 5000x g. Lysis was achieved in a Barocycler 2320XT pressure cycler by 60 pressure cycles consisting of 50 s at 45 kpsi, followed by 10 s at normal pressure. Next, samples were reduced and alkylated in a shaker at 600 rpm, using 5 mM of tris(2-carboxyethyl) phosphine and 20 mM iodoacetamide for 30 min at 30 C, diluted to urea concentration of 1.6 M and trypsinated (Promega, 1:20 enzyme-to-substrate ratio) using pressure cycling.

### 2.4 Proteome profiling: mass spectrometry

Prior to MS measurement, samples were reconstituted in 0.1% trifluoroacetic acid and 2% acetonitrile containing indexed retention time standard peptides, which, in combination with dynamic recalibration in the Spectronaut software, allows for correction of longitudinal retention time shifts and ensures accurate precursor matching between the library and study samples. For generation of a peptide library, 150 ug of peptide were pooled for each cavity including LA, RA, left ventricle (LV), right ventricle (RV) and septum, and separated into twenty fractions using a basic pH reversed phase C18 separation and a staggered pooling scheme.

Data-dependent analysis (DDA) of the fractionated cavity-specific pools was performed in PASEF mode, with ten scans per topN acquisition cycle as previous described. Three technical replicates (i.e. MS injection replicates) per C18 fraction were acquired.

400 ng equivalents of digested protein were analyzed on a nanoflow chromatography system coupled to a hybrid timed ion mobility-quadrupole-time of flight mass spectrometer (timsTOF Pro 2, Bruker, Bremen, DE) as previously described.

Data-independent analysis (DIA) of individual cardiac biopsies was performed in diaPASEF mode using a 100 min linear gradient and a customized 20 x 2 variable window size acquisition method covering ranges of m/z 350-1350 and 1/K0 = 0.7-1.5 Vs cm-2, respectively. Two technical replicates per sample were acquired.

### 2.5 Biochemical studies

Protein abundance was quantified by immunoblot as previously described, and normalized to calsequestrin.

### 2.6 Histology

The samples were fixed in 10% formalin and embedded in paraffin. Paraffin-embedded tissue blocks were cooled and sectioned at 2 um thickness using a sliding microtome. Masson-Goldner trichrome staining was performed on an automated stainer with integrated deparaffinization in xylene and rehydration through a graded ethanol series. Whole-slide images were acquired using an EVOS FL Auto 2 imaging system with a 10x objective. Quantification of intramuscular fibrosis (fibrotic area/total tissue area) was performed using ImageJ software.

### 2.7 Statistical and bioinformatics analysis

The Generalized Estimating Equations (GEE) model was applied using the 'geepack' R package for all comparisons of log2-transformed protein data. P values were adjusted for multiple testing using the Benjamini-Hochberg method via the 'p.adjust' function from the 'stats' package in R. Depending on the analysis, the dataset was pre-filtered based on indicated threshold and processed in Perseus v.1.6.15.0 for principal component analysis (PCA), Enrichr for enrichment analysis, and Cytoscape for protein-protein interaction networks.

To summarize medication burden, we constructed Drugs-PC1 as the first principal component of eight binary drug-use indicators (Digitalis, ACE inhibitors, AT1 blockers, beta-blockers, dihydropyridines, diuretics, nitrates, lipid-lowering drugs) after centering and scaling.

In addition to the primary (unadjusted) GEE, we refit models including covariates age, sex, Drugs-PC1, coronary artery disease (CAD), and mitral/aortic valve disease (MVD/AVD). Discovery thresholds and correction were unchanged (FDR < 0.05 together with |log2FC| > 0.58).

Plasma NT-proANP and NT-proBNP concentrations were analyzed with linear regression on log2-transformed values, contrasting persAF vs. SR. An adjusted specification included age, sex, CAD, valve disease, and diuretic use. Because only two biomarkers were tested, we report two-sided nominal P-values without multiplicity correction. Immunoblot data with sample size n >= 10 were tested for normality using the Shapiro-Wilk normality test. For datasets that followed a normal distribution, comparisons were performed using the unpaired two-tailed Student's t-test. Datasets with unequal variance were tested using the Welch's t test. For immunoblot data with sample size n < 10, comparisons were conducted using the Mann-Whitney U test. A P value < 0.05 was considered statistically significant.

## 3. Results

### 3.1 Differentially expressed proteins in RA-persAF

To assess the proteomic profile associated with persAF, we compared RA samples obtained from patients with SR (RA-SR; n = 15) and RA samples from patients with persAF (RA-persAF; n = 16).

Our analysis identified 21 differentially expressed proteins [FDR < 0.05 and |log2(FC)| > 0.58] in RA-persAF samples, of which 17 were up-regulated and 4 were down-regulated.

Baseline age and sex did not differ significantly between groups, and medication use across eight major drug classes was similar. Sensitivity analyses confirmed robustness: adjusting for overall medication burden (Drugs-PC1) yielded near-identical group-effect estimates (R2 = 0.969; RMSE = 0.034), and a fully adjusted model (Age, Sex, Drugs-PC1, CAD, MVD/AVD) produced tightly aligned effects (r = 0.917; RMSE = 0.082), with 16 proteins meeting discovery thresholds; nine overlapped the primary set and all shared the same direction of effect.

To support the reliability of the proteomic findings, we performed immunoblot validation in an independent patient cohort (SR, n = 16; persAF, n = 14).

### 3.2 Myolysis and extracellular matrix deposition

Furthermore, a marked decrease in cardiac contractile proteins was observed, including TNNC1, CRYAB, TPM1, TPM2, MYLK, MYH11, MYH14, MYL2, and TNNT2. This interpretation is reinforced by the fact that, when the dataset is pre-filtered for negatively abundant DEPs only, cardiac muscle contraction emerges among the most down-regulated biological processes. This is in accordance with previous publications linking myolysis and enhanced protein degradation processes with AF.

In RA-persAF, the most notable increase was in ECM proteins along with increased protein synthesis compartments, including ER and Golgi. In line with KEGG pathways/clusters, a notable loss in myofibrillar protein mass was observed in persAF. MYH6 and COL6A3 were the most altered myofibrillar and ECM proteins in RA-persAF, respectively.

In contrast, the cluster of ECM and receptor interaction demonstrated one of the most pronounced increases with robust enrichment in collagens and integrins. Proteins involved in ECM and receptor interaction appeared notably interconnected with up-regulated adhesion junction proteins, suggesting a potential crosstalk between the two pathways.

### 3.3 Similarity to the failing ventricular proteome

Overlapping up-regulated proteins were mainly associated with ECM (MFG-E8, COMP, PCOLCE2, TNXB, COL6A3, POSTN, DPT, VCAN, LTBP2, and HAPLN1).

Interestingly, the DCM pathway that emerged in the RA-persAF proteome, along with the up-regulation of other HF hallmarks NPPA and NPPB, pointed to shared features with HF. Consistently, NT-proANP and NT-proBNP were also significantly up-regulated in plasma samples from persAF patients compared with SR patients. Plasma NT-proANP levels remained significantly elevated after adjusting for age, sex, CAD, valve disease, and diuretic use, whereas NT-proBNP levels showed a similar trend but did not reach statistical significance following adjustment.

### 3.4 Fibrosis quantification

We further quantified atrial fibrosis relative to total tissue section in RA and LA using Masson-Goldner trichrome-stained paraffin sections from an independent patient cohort. This analysis revealed that both RA and LA from persAF patients exhibited significantly increased fibrosis compared with RA-SR controls, whereas no significant difference was observed between RA and LA within the persAF group. After covariate adjustment, the direction of the effect was preserved, though statistical significance was not reached, likely reflecting the limited sample size and variance imbalance (13 vs. 6, F-test = 0.049).

### 3.5 Atrial proteome homogenization in persAF

To compare AF-associated proteome remodelling in RA and LA, we next analysed paired RA and LA samples from 8 SR and 6 persAF patients.

In SR, PCA revealed a clear separation between RA and LA samples, indicating distinct protein abundance profiles.

This observation was confirmed by differential expression analysis. In SR, the number of differentially expressed proteins (DEPs) between RA and LA was significantly higher than in persAF. A total of 64 proteins showed higher abundance in the RA relative to the LA and 17 in the LA relative to the RA. Among the RA-enriched proteins were canonical RA markers commonly associated with low PITX2 activity, including CACNA2D2, HCN4, RGS6, NTM, and BMP10. In contrast, LA-SR was characterized by higher abundance of structural and mitochondrial proteins, including MYOT, FLNA, and ACSS1.

In contrast, in persAF, RA and LA samples showed considerable overlap in PCA, suggesting increased intra-atrial proteomic similarity.

In persAF, the number of DEPs in RA was reduced by 85%, while LA showed a 50% reduction.

In persAF, RA-specific BPs were markedly diminished, in line with the reduction in RA DEPs. Conversely, LA-specific metabolic pathways remained preserved or became even more prominent.

This pattern indicates that RA in persAF loses part of its distinct proteomic profile while acquiring LA proteome profile, thereby potentially contributing to greater similarity between chambers.

In RA-persAF, 61% of most abundant RA-SR proteins relative to LA-SR, including HCN4, CACNA2D2, NTM and RGS6, were down-regulated. Conversely, 47% of most abundant LA-SR proteins were up-regulated in RA-persAF.

Consistent with the proteomics data, immunoblot analysis confirmed that the RA-specific markers RGS6 and CACNA2D2 exhibited comparable abundance between RA and LA in persAF.

Overall, these results indicate that RA-persAF exhibits increased abundance of a subset of LA-SR enriched mitochondrial proteins, particularly those involved in fatty acid uptake (SLC27A1, ACAD11, ACOT9), energy metabolism (OXCT1, ALDH6A1, DHTKD1), and mitochondrial maintenance (ATAD3A, MTARC2) which may contribute to the observed atrial proteome unification.

The top LA-associated BP, 'Aerobic Electron Transport Chain' (GO:0019646), showed a highly significant enrichment in both SR (adj. P = 6.38 x 10-11) and persAF (adj. P = 1.03 x 10-12), indicating sustained mitochondrial activity in the LA.

## 4. Discussion

In this study, we investigated the AF-associated remodelling in RA relative to LA in persAF through a proteomic approach. To streamline the process and enhance the reproducibility of the analysis, we established a reference spectral library generated based on 5 anatomical regions from 5 independent donor hearts.

### 4.1 RA remodelling in persAF

PersAF-associated remodelling in the RA proteome reflects previously identified and well-established pathways that contribute to AF maintenance, including dysregulated protein homeostasis and increased ECM deposition.

The elevated protein load may be partially attributable to increased ECM production by activated myofibroblasts in response to mechanical stretch and inflammation. Fibrosis can lead to heterogeneous conduction and stabilize re-entrant drivers promoting AF.

Finally, the potential similarity between RA-persAF and failing ventricle appears to represent an important component of AF-associated remodelling. In contrast to transcriptomic studies, our findings did not reveal prominent commonalities between RA in persAF and healthy ventricle, but rather similarities with failing ventricle at the protein level.

It is important to highlight that the persAF patient cohort in this study had preserved left ventricular ejection fraction, supporting the notion that HF-associated features in the atria develop independently of ventricular dysfunction.

### 4.2 Determinants of RA-LA proteome symmetry in persAF

However, we observed a prominent overlap between RA and LA samples in persAF, suggesting enhanced atrial proteome symmetry. This pattern was further supported by comparable levels of fibrosis observed in both atria.

Our data suggest two major reasons for atrial proteome unification: (i) RA exhibits a shift toward a LA proteomic profile, while the LA remains relatively stable, and (ii) both atria acquire a disease-associated proteome profile to a comparable extent.

On the other hand, a comparable proteome between the two atrial chambers in persAF potentially suggests that both chambers may serve as equally vulnerable substrates promoting AF progression in the presence of widespread AF triggers.

### 4.3 Potential limitations

Although we were able to identify key proteins and processes differentially expressed between the compared groups (in substantial agreement with prior findings), our study relies on the RA and LA appendages, which may not fully represent RA and LA.

In addition, the number of paired RA and LA samples in this study is limited. Obtaining paired samples is exceptionally challenging, particularly in persAF patients without ventricular dysfunction or other comorbidities, such as mitral or coronary valve disease.

Although re-analysis of the Li et al. dataset markedly increased the number of detected proteins, the comparison with our persAF dataset may be influenced by technical differences in data acquisition and processing, in addition to variations in proteome coverage (6875 vs. 4456).

We would like to acknowledge that the whole tissue extract provides a global disease signature but lacks cell type-specific markers and mechanisms. This approach may also mask the abundance of less abundant proteins, such as transcription factors (PITX) or ion channels, and the latter could benefit from membrane fractionation prior to MS analysis.

Moreover, it is important to note that many ion channels and Ca2+ handling proteins exhibit altered activity in AF primarily due to enhanced phosphorylation rather than changes in abundance levels.

### 4.4 Conclusions and potential significance

However, our findings indicate that the RA proteome exhibits the hallmark characteristics of persAF at comparable levels to LA, reflecting a global atrial unification and reinforcing the view that persAF is a biatrial disease.

Most of rate and rhythm control strategies target both, the RA and LA simultaneously (antiarrhythmic drugs, AV node ablation, cardioversion). However, catheter ablation—first-line antiarrhythmic therapy for selected patients—is predominantly used to ablate the PV in the LA.

Due to lack of large randomized studies, variability in non-PV triggers (ranging from 5 to 69%) and varying definitions of non-PV triggers in between studies, determining the benefit of targeting non-PV triggers remains challenging.

Furthermore, the incidence of non-PV foci has been shown to positively correlate with AF progression, with rates increasing from 2.9% in pAF to 19.1% in long-standing persAF, indicating their evolution over time if left untreated.

## Translational perspective

Management of persistent atrial fibrillation (persAF) remains challenging and often accompanied by high recurrence rates. A deeper understanding of the mechanisms underlying AF maintenance is therefore essential to refine antiarrhythmic strategies.

While left atrium is the traditional therapeutic target due to its central role in AF initiation, our findings suggest that persistent AF is also associated with major changes in the right atrium.

Key AF-associated remodelling features, including fibrosis, myolysis, metabolic alterations, and failing ventricle-like characteristics were reflected at comparable levels in right and left atrial proteomes. These observations suggest that right atrium warrants greater attention in clinical management.`;

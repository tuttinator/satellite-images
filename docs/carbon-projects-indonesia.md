# Forest-carbon projects in Indonesia and where to get their boundaries

Compiled 23 Aug 2026 from three research passes over the Verra, Gold Standard and Plan Vivo
registries, ID-RECCO, the Ministry of Forestry's geoportals, Global Forest Watch, Ina-Geoportal and
secondary sources. "Verified" means the URL was fetched that day. Items marked *(unverified)* are
from recollection or secondary sources only.

## TL;DR — the two sources that actually give polygons

1. **Verra registry KMLs** (accounting boundaries of credited projects). The registry moved to an
   S&P-hosted platform in July 2026 and the website is a JS shell to scripts, but its public API
   works: `scripts/fetch_verra_kml.py <VCS ids>` downloads the registry record and every KML in the
   document list. 38 of the 42 Indonesian AFOLU projects have a KML. Two are already loaded in
   `data/concessions.geojson` (Katingan 149,704 ha, Rimba Raya 64,183 ha).
2. **Ministry of Forestry PBPH shapefile** (licence boundaries of all forestry concessions —
   logging, plantation and the legacy ecosystem-restoration concessions). 608 polygons, Dec 2023,
   public download, no login:
   `curl -L -o pbph.zip "https://spatial.phl.kehutanan.go.id/portal/sharing/rest/content/items/455c9a4ca3194d4fb12c66345bb3dd75/data"`
   Fields: `NAMOBJ, NO_SK, TGL_SK, KODE_PROV (BPS code), JENIS, STAT_IZIN (Aktif/Dicabut/Berakhir), REMARK`.
   Legacy RE holders carry `REMARK = "SK Perubahan Nomenklatur"`. PT Rimba Makmur Utama (2 units,
   157,404 ha, Aktif) and PT Rimba Raya Conservation (37,161 ha, **Dicabut**) are in it and now
   in `data/concessions.geojson`.

Everything else (GFW, ID-RECCO, Plan Vivo, Gold Standard, SRN) is attribute data, out of date, or
has no downloadable geometry — details below.

## Government geospatial portals (state of play)

| Portal | URL | Status / what it offers |
|---|---|---|
| **SIGAP Kehutanan** (replaced geoportal.menlhk.go.id, relaunched Oct 2025) | https://sigap.kehutanan.go.id/ ; map app: https://geoportal.planologi.kehutanan.go.id/portal/apps/experiencebuilder/experience/?id=46d3d0cc19504604ade2064c7341d2c2 | Front-end viewer only. Shapefile/GDB downloads are by written request to Dit. IPSDH and only for government/academia; the public gets JPG/PDF "Peta Cetak" sheets and the REST services below. |
| **Kemenhut ArcGIS Server** (the data behind SIGAP) | https://geoportal.planologi.kehutanan.go.id/server/rest/services?f=pjson | ~37 public MapServers, no login. Folder `Peta_Interaktif_2026`: `PBPH_AR_50K` (May 2026, 541 records — **attributes only, geometry returns null**), `PAPH_AR_250K`, `KWSHUTAN_AR_250K` (forest estate, Jun 2026, map-only), `PL_AR_250K` (land cover 2024), `PIAPS`, `PIPPIB_2026_I` (moratorium), `PPKH`, `HUTAN_ADAT`, `KPH`, `ZONA_TN`, `DAS`, `LAHAN_KRITIS`, `RENJA_FOLU_2030`, deforestation/reforestation, hotspots. Query pattern: `.../MapServer/0/query?where=1%3D1&outFields=*&f=geojson&returnGeometry=true&resultOffset=N` (2000 per page). WMS/WFS disabled. |
| **Ditjen PHL portal** | https://spatial.phl.kehutanan.go.id/ | Hosts the downloadable PBPH shapefile above. Its feature services are broken (web-adaptor SSL error); use the item download. |
| Ina-Geoportal / One Map (BIG) | https://tanahair.indonesia.go.id/portal-web/ | Base data only (RBI admin, DEMNAS, BATNAS). Downloads need registration (email/WA OTP). No concession or forest-estate layers. BIG REST: https://geoservices.big.go.id/rbi/rest/services |
| Kebijakan Satu Peta | https://satupeta.go.id/ | Policy site; compiled thematic maps are inter-agency only. |
| SRN-PPI (national climate registry) | https://srnindonesia.kemenlh.go.id (new; dashboards currently empty). `srn.kemenlh.go.id` shows a defacement/maintenance page; `srn.menlhk.go.id` DNS dead. | Not usable for a FOLU project list right now. |
| IDX Carbon | https://www.idxcarbon.co.id/product-spe-grk | 10 listed SPE-GRK projects, all energy. No forestry. |

Note on terminology: under PP 23/2021 every forestry licence became a **PBPH**. "Ecosystem
restoration concession" (IUPHHK-RE) no longer exists as a map category. Legacy RE holders are coded
like logging concessions (`PHHK_HP`) with the nomenclature-change remark; newer carbon-style
concessions are coded `PJL_HP` (jasa lingkungan). The May-2026 PBPH layer has 55 `PJL`-type records
(~1.59 Mha), most flagged "BELUM PAK" (working area not yet finalised), that are not yet on any
registry.

Dead hostnames (don't bother): geoportal.menlhk.go.id, geoportal.kehutanan.go.id, sigap.menlhk.go.id,
webgis.menlhk.go.id, phpl.menlhk.go.id, spatial.phl.menlhk.go.id, sipuhh.menlhk.go.id,
pusdatin.kehutanan.go.id, kepohutan.greenpeace.org, portal.ina-sdi.or.id.

## Other boundary sources

| Source | URL | Coverage | Format | Vintage | Terms | Notes |
|---|---|---|---|---|---|---|
| GFW – Indonesia logging concessions | https://data.globalforestwatch.org/datasets/0667ff7b2776441b805b98d3dbe9cbbc_0 | 559 polygons, `name, area_ha, permit_num` — no RE flag | SHP/GeoJSON/KML; FeatureServer | MoF 2010 | none stated; Data API excludes Indonesia from CC BY | `https://opendata.arcgis.com/api/v3/datasets/0667ff7b2776441b805b98d3dbe9cbbc_0/downloads/data?format=geojson&spatialRefId=4326` |
| GFW – wood fibre concessions | https://data.globalforestwatch.org/datasets/indonesia-wood-fiber-concessions | 539 HTI polygons | SHP | Sept 2018 | "view only" | |
| GFW – oil palm concessions | https://data.globalforestwatch.org/datasets/indonesia-oil-palm-concessions | 1,845 polygons, incomplete | SHP/GeoJSON/KML | 2011/12 | custom | |
| GFW – peat lands | https://data.globalforestwatch.org/datasets/indonesia-peat-lands | 1,524 polygons | MapServer `…/country_data/asia/MapServer/10` | 2019 | — | Hub download currently broken; query MapServer |
| GFW – forest moratorium / forest area | (view-only, API key for download) | — | — | 2017–2020 | — | Use Kemenhut `PIPPIB_2026_I` / `KWSHUTAN_AR_250K` instead |
| GFW – ecosystem restoration concessions | **does not exist** | | | | | |
| Trase Open Data – HTI concessions | https://trase.earth/open-data | Pulp concessions | download | MoF 2025 | CC BY 4.0 | Only recent open concession set; no HA/RE |
| Auriga Nusantara / SimonTini | https://simontini.id/en/download | Annual deforestation polygons 2023–25 | SHP zips | 2023–25 | CC BY-SA | concessions map-only |
| WDPA (protected areas) | EE `WCMC/WDPA/current/polygons` | Sebangau, Tanjung Puting etc. | EE / SHP | current | UNEP-WCMC | Already used for the park outlines |
| CarbonPlan OffsetsDB | https://carbonplan-offsets-db.s3.us-west-2.amazonaws.com/production/latest/offsets-db.csv.zip | All Verra/GS/ACR/CAR projects, metadata | CSV | 2026-06-01 | CC BY *(unverified)* | No geometry; easiest list of Indonesian project IDs |
| Berkeley Voluntary Registry Offsets Database | https://gspp.berkeley.edu/assets/uploads/page/Voluntary-Registry-Offsets-Database--v2026-06.xlsx | same | XLSX | Jun 2026 | academic | No geometry |
| ID-RECCO | https://www.reddprojectsdatabase.org/country/indonesia/ ; open copy DOI 10.17528/CIFOR/DATA.00272 | 58 Indonesian REDD+ entries | XLSX (login) | Dec 2023 | CC BY 4.0 (Dataverse copy) | One point coordinate per project, no polygons |
| IGES REDD+ database | https://redd-database.iges.or.jp | retired pilots (Ulu Masen, KFCP, MRPP) | PDF maps | 2008–14 | — | |
| Nusantara Atlas | https://nusantara-atlas.org | concessions + alerts | web map, premium | — | non-commercial, no redistribution | |
| Gold Standard API | `https://public-api.goldstandard.org/projects?countries=ID` (needs browser User-Agent); docs `https://assurance-platform.goldstandard.org/api/public/project-documents/GS<id>` | 33 Indonesian projects, 7 land-use | JSON; document download `…/api/public/documents/<uuid>/download` | current | public | Only one boundary file found (GS23180 Sumatra-1 mangrove, 143 ha KML) |
| Plan Vivo | https://www.planvivo.org/projects/carbon ; IHS Markit registry | 3 certified + pipeline | PDFs only | current | — | No KML/SHP anywhere |

## Verra VCS — Indonesian AFOLU projects (42 found of 47 the registry reports)

Status as of 23 Aug 2026. "KML doc id" is the document id to pass to the Verra download endpoint
(`scripts/fetch_verra_kml.py` does this for you by VCS id). Area is as recorded in the registry.

| VCS | Name | Proponent | Location | ha | Status | Type / method | KML doc id |
|---|---|---|---|---|---|---|---|
| 674 | Rimba Raya Biodiversity Reserve | InfiniteEARTH | C. Kalimantan, Seruyan | 64,977 (accounting 47,237) | Late to Verify; licence revoked 2023, upheld Jul 2026 | REDD / VM0004 | 110200000270012 |
| 1477 | Katingan Peatland Restoration & Conservation | PT Rimba Makmur Utama | C. Kalimantan, Katingan & Kotim | 149,800 (registry shows 14,980 — migration error) | Registered; approved for export Jul 2026 | ARR, REDD, WRC / VM0007 | 110200000381922 (+4 sub-area KMLs) |
| 1493 | Mangrove restoration E. coast Aceh & N. Sumatra | Livelihoods Fund / Yagasu | Aceh, N. Sumatra | 1,000–5,000 | Verification requested | ARR / AR-AM0014, VM0033 | 110200000314214 |
| 1498 | Kampar Peninsula peat swamp | KPHP Tasik Besar Serkap | Riau, Siak | 14,723 | Under validation | REDD / VM0007 | 110200000274633 |
| 1899 | Sumatra Merang Peatland Project | Forest Carbon / PT Global Alam Lestari | S. Sumatra, Musi Banyuasin | 22,922 | Registered; approved Jul 2026 | ARR, WRC / VM0007 | 110200000381622 |
| 2395 | OKI REDD+ | YL Forest Co. | S. Sumatra, OKI | 23,500 | Registration requested | ARR / VM0007 | 110200000336848 |
| 2403 | Riau Ecosystem Restoration | APRIL / RER | Riau, Kampar Peninsula | 130,090 | Verification requested | REDD, WRC / VM0007 | 110200000317175 |
| 3012 | Agroforestry & Reforestation | PUR Projet | Aceh, Babel, W. Java, SE Sulawesi | 515 | Registration requested | ARR / AR-AMS0007 | 110200000333283 |
| 3226 | Padang Tikar Landscape | PT Belantara Sejahtera Mandiri | W. Kalimantan, Kubu Raya | 58,673 | Withdrawn (→ 5834) | REDD, WRC | 110200000355898 |
| 3587 | Kopi Lestari Agroforestry | PUR Projet | Aceh Gayo, Lampung | 2,400 | Inactive | ARR | — |
| 3591 | The Mayas Project | PT Mohairson Pawan Khatulistiwa | W. Kalimantan, Ketapang | 33,747 | Registration requested; approved Jul 2026 | REDD, WRC / VM0007 | none (4 docs, no KML) |
| 4186 | Gorontalo corn→cacao REDD | Kanematsu | Gorontalo | 43,014 | Rejected | REDD | — |
| 4381 | West Seram REDD+ & Agarwood | Asia Assets Developments | Maluku | 37,875 | Under validation | ARR, REDD / VM0047 | 110200000347144 |
| 4520 | Muara Teweh Conservation | PT Austral Byna / Fairatmos | C. Kalimantan, Barito Utara | 255,700 | Under development | IFM / VM0010 | 110200000288242 |
| 4782 | South Barito Kapuas | PT Nusantara Raya Solusi | C. Kalimantan | 39,835 | Registration requested | ARR, REDD, WRC | 110200000370916 |
| 4967 | PLUM Peat & Mangrove | PT Pagatan Usaha Makmur | C. Kalimantan, Katingan | 23,247 | Registration requested | ARR, REDD, WRC | 110200000282386 |
| 5032 | Kupu-Kupu mangrove silvofishery | Vlinder | S. Sulawesi | 66,700 | Under development | ARR, WRC / VM0033 | 110200000352279 |
| 5283 | SERCOVA | PT Strata Pacific | Maluku, E. Seram | 73,365 | Registration requested | IFM / VM0010 | 110200000350342 |
| 5371 | Kubu Peatland | Menggala Rambu Utama | W. Kalimantan, Kubu Raya | 20,155 | Registration requested | REDD, WRC | 110200000281061 |
| 5448 | BlueRizon Java-1 | Apolownia | N. Java | 3,200 | Under validation | ARR, WRC / VM0033 | 110200000323396 |
| 5458 | Sanggala Corridor | PT CarbonX Bumi Harmoni | W. Kalimantan, Sanggau & Landak | 16,285 | Registration requested | ARR, REDD | 110200000381440 |
| 5475 | Kuburaya Mangrove | PT Nusantara Climate Initiative (PT Kandelia Alam) | W. Kalimantan, Kubu Raya | 18,042 | Under validation | IFM, REDD, WRC | 110200000383772 |
| 5520 | Pekanbaru Suntara Peatland | Indacom | Riau, Dumai | 35,644 | Under validation | ARR, REDD, WRC | 110200000289152 |
| 5524 | Central Seram IFM | Asia Assets Developments | Maluku | 57,548 | Under validation | IFM / VM0010 | 110200000292706 |
| 5545 | YAKOPI Mangrove Restoration | YAKOPI / ClimeCo | Aceh, N. Sumatra | 1,100 | Under development | ARR, WRC / VM0033 | 110200000295223 |
| 5585 | Project Lestari | PT Agra Inti Investama | N. Kalimantan, Malinau | 60,000 | Under development | REDD | 110200000318569 |
| 5620 | Carbon Agroforestry Java | EVI Green Markets / Yagasu | Java | 78 | Under validation | ARR / VM0047 | 110200000288681 |
| 5631 | Enviro Rise | PT Rimbun Seruyan | C. Kalimantan, Seruyan | 34,250 | Under development | ARR, REDD, WRC | 110200000278147 |
| 5695 | Siluk Peatlands Conservation | PT Annisa Surya Kencana | W. Kalimantan, Kapuas Hulu | 28,506 | Under validation | REDD, WRC | 110200000341879 |
| 5722 | Jati Dharma Indah IFM 1 | CERPD | C. Papua, Nabire | 169,657 | Under development | IFM / VM0010 | 110200000361627 |
| 5736 | Kapuas Pisau Conservation | PT Indo Hutan Ekosistem | C. Kalimantan, Kapuas / Pulang Pisau | 13,580 | Under validation | ARR, REDD, WRC | none |
| 5796 | Tanimbar Community Forest Restoration | Asia Assets Developments | Maluku | 54,976 | Under validation | ARR / VM0047 | 110200000353200 |
| 5798 | Kaltim Hutama IFM | CERPD | Papua | 141,849 | Under development | IFM / VM0010 | 110200000366517 |
| 5799 | Gerbang Barito REDD+ | Wildlife Works / LPHD | C. Kalimantan, Barito Selatan | 19,752 | Under development | REDD, WRC | 110200000292643 |
| 5834 | Delta Kapuas | PT Belantara Sejahtera Mandiri | W. Kalimantan, Kubu Raya & Kayong Utara | 122,120 | Under development | ARR, REDD, WRC | 110200000340571 |
| 5845 | Nunukan Mangrove & Peatland | PT Bumi Hijau Konservasi | N. Kalimantan | 15,591 | Under validation | ARR, REDD, WRC | 110200000284777 |
| 5873 | Gunung Lumut Landscape | PT Telaga Mas Kalimantan | E. Kalimantan, Paser | ~116,000 (registry shows 116) | Under development | ARR, IFM, REDD | 110200000293838 |
| 5891 | Forest Landscape Restoration N. Sulawesi | Thryve.Earth | N. Sulawesi | 6,000 | Under validation | ARR / VM0047 | 110200000302090 |
| 5905 | Gunung Mas Community Forest Restoration | Asia Assets Developments | C. Kalimantan, Gunung Mas | 44,214 | Under validation | ARR / VM0047 | 110200000272093 |
| 5956 | AgriCapture SE Asia Rice Methane | AgriCapture | Lombok | 3,000 | Under development | ALM (not forest) | 110200000354127 |
| 6085 | Murung Raya IFM | PT Samudera Rejeki Perkasa | C. Kalimantan, Murung Raya | 87,543 | Under development | IFM / VM0010 | 110200000308546 |
| 6128 | Kapuas Hulu IFM | Hong Kong Fine Technology | W. Kalimantan | 43,810 | Pipeline listing requested | IFM | — |

Central Kalimantan alone has 11 of these (674, 1477, 4520, 4782, 4967, 5631, 5736, 5799, 5905,
6085, plus Sebangau-adjacent 5736) — worth loading all of them into the viewer.

## Projects on social-forestry land (not concessions, not yet on a registry)

**CarbonEthics "Pulang Pisau PRESERVE"** (ARR + WRC, "21,000+ ha", four villages: Pilang, Simpur,
Tumbang Nusa, Henda; Jabiren Raya sub-district, Pulang Pisau regency, on the Kahayan river east of
Sebangau NP). Not on Verra, Gold Standard or Plan Vivo under any name as of Aug 2026; the site
offers "pre-purchase credits", i.e. pre-registration. It is **not** VCS 5736 "Kapuas Pisau
Conservation" (PT Indo Hutan Ekosistem, 13,580 ha, the former PT Ramang Agro Lestari timber
concession in Mantangai / Banama Tingang — different villages, different land status).

The land is **Hutan Desa (village forest)** social-forestry permits, which the Ministry serves as
polygons from `Peta_Interaktif_2026/PPHD_AR_50K`:

| Village | Permit holder | Decree | ha |
|---|---|---|---|
| Pilang | LPHD Pilang | SK.10868/MENLHK-PSKL/PKPS/PSL.0/12/2019 | 8,583 |
| Henda | LPHD Henda | SK.10838/…/12/2019 | 3,932 |
| Tanjung Taruna | LPHD Tanjung Taruna (+2 LDPH, 2024) | SK.10837/…/12/2019; 13527/13529 (2024) | 4,858 (+4,756, +2,232) |
| Tumbang Nusa | LDPH Nusa Indah | 13531 TAHUN 2024 | 3,420 |

Pilang + Henda + Tanjung Taruna + Tumbang Nusa = 20,793 ha, matching "21,000+". Simpur has no
village-forest permit in the 2026 layer. All 487 Kalimantan village forests are in
`data/context.geojson` (`kind = village_forest`), built by `scripts/build_context.py`.

Also on that server and worth using: `Areal_Kebakaran_Hutan_dan_Lahan_Periode_Berjalan` (the
Ministry's own current-season burned-area polygons) and `SEBARAN_HOTSPOT_KAWASAN_HUTAN_BULANAN`.

## Other standards and non-registry projects

| Project | Scheme / ID | Proponent | Location | ha | Status | Boundary |
|---|---|---|---|---|---|---|
| Bujang Raba Community PES | Plan Vivo | KKI Warsi | Jambi, Bungo | >5,000 | Certified 2013; approved for export Jul 2026 | none public |
| Nanga Lauk | Plan Vivo | PRCF Indonesia | W. Kalimantan, Kapuas Hulu | ~12,800 | Certified 2016 | none |
| Gula Gula Food Forest | Plan Vivo | CO2operate | W. Sumatra | ~109 | Certified 2019 | none |
| Durian Rambun | Plan Vivo | KKI Warsi | Jambi, Merangin | 3,616 | Decertified Apr 2025 | none |
| Leuser highlands agroforestry | GS13164 | Livelihoods Carbon Fund | Aceh | 11,800 | Listed | none public |
| Ibu Bakau mangrove PoA | GS23213–15 | Value Network Ventures / YAGASU | Sumatra | 1,171 (VPA-2) | Listed / design cert. | none public |
| Global Mangrove Trust Blue Carbon | GS23179–80 | Global Mangrove Trust | N. Sumatra / Aceh | 143 (VPA-1) | Certified design | KML: `https://assurance-platform.goldstandard.org/api/public/documents/59f0c757-5b0a-4cc7-baf2-84250b2d65a7/download` |
| Harapan Rainforest | ERC only, no credits | PT REKI (Burung Indonesia / RSPB / BirdLife) | Jambi + S. Sumatra | ~98,555 | Active | PBPH shapefile (2 records) |
| Bukit Tigapuluh ERC | ERC only | PT Alam Bukit Tigapuluh (WWF / FZS) | Jambi, Tebo | 38,665 | Active | not found by name in PBPH layers — check Dec-2023 file |
| Kehje Sewen | ERC only | PT RHOI (BOS Foundation) | E. Kalimantan | 86,450 | Active | PBPH shapefile |
| PT Ekosistem Khatulistiwa Lestari | ERC | PT EKL | W. Kalimantan, Kubu Raya | 14,080 | Active | PBPH shapefile |
| Ulu Masen | CCB 2008 (expired) | Aceh Govt / FFI | Aceh | ~750,000 | Retired | PDF map only |
| Berau Forest Carbon Program | jurisdictional | TNC → YKAN | E. Kalimantan | district | Ongoing 2025–30 | district boundary |
| East Kalimantan FCPF ER Program | FCPF Carbon Fund | GoI / BPDLH | E. Kalimantan | province | Closing Dec 2025 | province boundary |
| KFCP, Merang pilot (MRPP) | demo | Australia / GIZ | C. Kalimantan / S. Sumatra | 120,000 / 24,000 | Retired | PDF maps only |
| Mawas | ID-RECCO 520 | BOSF | C. Kalimantan | 240,000 | Ongoing (no registry) | none |

Historic IUPHHK-RE holders (16 units, ~623,075 ha, Oct 2018; Silalahi et al. 2020): PT REKI (Sumsel
52,170; Jambi 46,385), PT RHOI 86,450, PT EKL 14,080, PT Gemilang Cipta Nusantara I & II 20,265 +
20,450, PT Rimba Makmur Utama I & II 108,255 + 49,620, PT Rimba Raya Conservation 36,954, PT SIPEF
Biodiversity Indonesia 12,656, PT Sinar Mutiara Nusantara 32,830, PT Global Alam Nusantara 36,850,
PT The Best One Unitimber 39,412, PT Karawang Ekawana Nugraha 8,300, PT Alam Bukit Tigapuluh 38,665,
PT Alam Sukses Lestari 19,520.

## Things that could not be verified

- Verra's list/search endpoints return HTTP 500; the 42 projects were assembled from Berkeley VROD,
  CarbonPlan OffsetsDB and an ID sweep (ranges 393–1999 and 2500–5573 were not swept), so up to
  5 Indonesian AFOLU projects may be missing.
- Registry areas for 1477 (14,980) and 5873 (116) look like migration truncation; corrected
  values come from the project KML (149,704 ha measured) and secondary sources.
- Gold Standard statuses/areas are from Berkeley VROD, not the GS registry itself.
- Plan Vivo registry (IHS Markit) was not checked; areas other than Bujang Raba are from ID-RECCO.
- PT Rimba Raya Conservation, PT Alam Bukit Tigapuluh and PT Gemilang Cipta Nusantara are absent
  from the May-2026 PBPH service by name (revoked/renamed/merged?) — Rimba Raya *is* in the
  Dec-2023 shapefile with `STAT_IZIN = Dicabut`.
- PT Gunung Gajah Abadi is a logging concession (RIL-C partner), not a carbon project.
- Licence terms for the PBPH shapefile and the Kemenhut REST services are not stated anywhere;
  treat as public-sector data with attribution to Kementerian Kehutanan, and don't redistribute
  without checking.

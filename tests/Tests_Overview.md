# Test Suite Subsystem Overview

The `/tests` directory houses the automated test suite built with `pytest`. It delivers end-to-end testing of logging, game engine loops, night action priorities, community moderation, narration fallbacks, and parameter boundaries.

## 🧭 Navigation
- **Parent Hub**: [[Root_Project_Overview]]
- **Related Modules**: [[Game_Engine_Overview]], [[Game_Actions_Overview]], [[Community_System_Overview]], [[Utilities_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-10-Quality-Assurance--Automated-Testing]], [[DETAILED_REQUIREMENTS#4-Test-Strategy--Verification-Plan]]

---

## 🧪 Test Suite Index

| Test Module | Coverage Domain | Key Verifications |
| :--- | :--- | :--- |
| `test_0_logging.py` | Logging & Setup | Verifies file rotators, debug/error splits, and logger setup without crashes. |
| `test_1_engine.py` | Game Engine State Machine | Tests player signups, leave mechanics, phase transitions, and state persistence. |
| `test_2_action.py` | Night Actions & Priority | Verifies Block -> Heal -> Kill -> Investigate priority, Godfather immunity, and Doctor saves. |
| `test_3_community.py` | Community Quirks & UI | Tests quirk validation, pending queue, admin approval/rejection, and UI modals. |
| `test_4_narration.py` | Narration Engine | Tests Gemini API payload formatting, theme injections, and static fallbacks. |
| `test_5_statistics.py` | Stats & Skill Score | Verifies career calculations, leaderboard rankings, and Skill Score formulas. |
| `test_6_utilities.py` | Utility Functions | Tests message chunkers, JSON atomic writers, role hierarchy sorting, and time formatters. |
| `test_7_parameters.py` | Parameter Validation | Tests boundary limits on phase lengths, player thresholds, and invalid inputs. |
| `test_8_invariants.py` | 15 Game Invariants QA | Covers Mafia team reveals, phase transitions, join locks, concurrency, graceful error messages, vote clearing, dead player targeting, display names, doctor self-heal, narration role secrecy, and dead cop reports. |
| `test_sheets_setup.py` | Google Sheets Rules Logging | Verifies sync & async export of rules configuration to the Rules Setup worksheet tab. |
| `test_themes_and_skins.py` | Themes & Role Reskins QA | Verifies all 9 themes in `themes.json` and `theme_roles.json`, mechanical name preservation vs display skins, non-death static narration (Rom Com & Office Restructuring), AI prompt rubrics, and game status formatting. |
| `test_randomness.py` | RNG Distribution | Asserts unbiased role distribution across 10,000 simulated setups. |
| `test_sandbox.py` | Sandbox & Isolation | Validates headless mock discord objects and environment isolation. |

---

## 🏃 Running Tests
```bash
pytest tests/ -v
```

---

## 🔗 Connected Overviews
- [[Root_Project_Overview]]: Return to Master Hub
- [[Game_Engine_Overview]]: The primary system validated by these tests
- [[Game_Actions_Overview]]: Night action logic verified in `test_2_action.py`

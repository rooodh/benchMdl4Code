#!/usr/bin/env python3
"""
Validator Playwright pour recipe-book.
Reçoit : workdir port [python_path]
Retourne : exit 0 (succès) ou exit 1 (échec) ou exit 2 (env problem)
"""
import subprocess
import sys
import time
import os

def wait_for_server(port=8000, timeout=30):
    import urllib.request
    import urllib.error
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f"http://localhost:{port}", timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False

def main():
    if len(sys.argv) < 3:
        print("Usage: recipe-book.py <workdir> <port> [python_path]")
        sys.exit(1)

    workdir = sys.argv[1]
    port = int(sys.argv[2])
    python_bin = sys.argv[3] if len(sys.argv) > 3 else sys.executable

    try:
        import importlib.util
        if importlib.util.find_spec("playwright") is None:
            raise ImportError("playwright")
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed.")
        print("Fix: pip install playwright && playwright install chromium")
        sys.exit(2)

    # Démarrer l'application
    print(f"Starting app in {workdir} on port {port} (python: {python_bin})...")
    proc = subprocess.Popen(
        [python_bin, "main.py"],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PORT": str(port)}
    )

    if not wait_for_server(port=port, timeout=30):
        print("ERROR: Server did not start within 30s")
        stdout, stderr = proc.communicate(timeout=2)
        print("STDOUT:", stdout.decode()[:500])
        print("STDERR:", stderr.decode()[:500])
        proc.kill()
        sys.exit(1)

    print("Server is up.")

    success = True
    failed_tests = []
    base_url = f"http://localhost:{port}"

    def wait_for_any(page, selectors, timeout=10000):
        """Attend que l'un des sélecteurs apparaisse et retourne le premier trouvé."""
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=timeout)
                return sel
            except Exception:
                continue
        return None

    def count_items(page, selectors):
        """Compte les éléments en essayant plusieurs sélecteurs."""
        for sel in selectors:
            try:
                items = page.locator(sel).all()
                if len(items) > 0:
                    return len(items), sel
            except Exception:
                continue
        return 0, None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Sélecteurs candidats pour les cards de recettes (larges)
            CARD_SELECTORS = [
                ".recipe-card", ".card", "[class*='recipe']", "[class*='card']",
                "#recipeList > div", "#recipeList > li", "#recipeList > article",
                ".recipes > div", ".recipes > li",
                "main div[onclick]", "[data-id]",
                ".recipe-item", ".recipe",
            ]
            # Sélecteurs pour déclencher la navigation vers le détail
            CLICK_SELECTORS = [
                ".recipe-card", ".card", "[class*='recipe-card']",
                "#recipeList > div", "#recipeList > li",
                "[data-id]", "[onclick]", ".recipe-item",
                "a[href*='recipe']", "a[href*='detail']",
            ]
            # Sélecteurs pour le bouton portions
            PORTIONS_SELECTORS = [
                "#portionsSelect", "select[id*='portion']", "select[id*='serving']",
                "button:has-text('x2')", "button:has-text('×2')",
                "[data-multiplier='2']", ".portion-btn",
            ]
            # Sélecteurs pour les quantités d'ingrédients
            QTY_SELECTORS = [
                "[class*='quantity']", "[class*='amount']", "[data-base]",
                ".ingredient-qty-display", ".qty", "td:first-child",
                ".ingredient span:first-child",
            ]
            # Sélecteur bouton ajout recette
            ADD_BTN_SELECTORS = [
                "button:has-text('Ajouter une recette')", "button:has-text('Ajouter')",
                "a:has-text('Ajouter')", "[href*='add']", "[href*='new']",
                "#addRecipeBtn", ".add-recipe",
            ]
            # Sélecteur submit formulaire
            SUBMIT_SELECTORS = [
                "button[type='submit']", "button:has-text('Enregistrer')",
                "button:has-text('Sauvegarder')", "button:has-text('Créer')",
                "input[type='submit']",
            ]

            # ── Test 1 — Liste non vide ──────────────────────────────────────
            print("\n[Test 1] Liste des recettes non vide...")
            page.goto(base_url)
            page.wait_for_load_state("networkidle", timeout=10000)
            # Attendre que le JS rende quelque chose
            matched_sel = wait_for_any(page, CARD_SELECTORS, timeout=8000)
            n, used_sel = count_items(page, CARD_SELECTORS)
            if n >= 1:
                print(f"  PASS — {n} recette(s) [{used_sel}]")
            else:
                # Dernier recours : contenu texte contient-il des recettes ?
                content = page.content()
                if any(word in content for word in ["recette", "recipe", "Recette"]):
                    print(f"  PASS (text fallback) — contenu recette détecté")
                    n = 1
                else:
                    print(f"  FAIL — aucune recette trouvée (sélecteurs: {CARD_SELECTORS[:3]}...)")
                    success = False
                    failed_tests.append("Test 1: liste vide")

            # ── Test 2 — Navigation vers le détail ──────────────────────────
            print("\n[Test 2] Navigation vers le détail...")
            try:
                page.goto(base_url)
                page.wait_for_load_state("networkidle", timeout=10000)
                wait_for_any(page, CARD_SELECTORS, timeout=8000)

                clicked = False
                for sel in CLICK_SELECTORS:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.click(timeout=5000)
                            clicked = True
                            break
                    except Exception:
                        continue

                if not clicked:
                    raise Exception("Aucun élément cliquable trouvé pour naviguer vers le détail")

                page.wait_for_load_state("networkidle", timeout=10000)

                # Vérifier présence d'ingrédients et étapes (texte ou DOM)
                content = page.content()
                has_ingredients = (
                    page.locator("[class*='ingredient'], .ingredients, #ingredients").count() > 0
                    or "ingrédient" in content.lower() or "ingredient" in content.lower()
                )
                has_steps = (
                    page.locator("[class*='step'], .steps, #steps, ol").count() > 0
                    or "étape" in content.lower() or "step" in content.lower()
                )

                if has_ingredients and has_steps:
                    print(f"  PASS — ingrédients={has_ingredients}, étapes={has_steps}")
                else:
                    print(f"  FAIL — ingrédients={has_ingredients}, étapes={has_steps}")
                    success = False
                    failed_tests.append("Test 2: détail incomplet")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 2: {e}")

            # ── Test 3 — Ajustement des portions ────────────────────────────
            print("\n[Test 3] Ajustement des portions...")
            try:
                # On est déjà sur le détail, sinon y revenir
                content_before = page.content()

                matched = wait_for_any(page, PORTIONS_SELECTORS, timeout=5000)
                if matched is None:
                    raise Exception("Sélecteur portions introuvable")

                el = page.locator(matched).first

                # Récupérer une valeur avant
                qty_before = ""
                for qs in QTY_SELECTORS:
                    try:
                        qel = page.locator(qs).first
                        if qel.count() > 0:
                            qty_before = qel.inner_text(timeout=2000)
                            break
                    except Exception:
                        continue

                # Déclencher le changement selon le type d'élément
                tag = el.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    # Sélectionner x2 ou la 2e option
                    try:
                        el.select_option("2")
                    except Exception:
                        options = el.locator("option").all()
                        if len(options) >= 2:
                            options[1].evaluate("el => el.selected = true")
                            el.evaluate("el => el.dispatchEvent(new Event('change'))")
                else:
                    el.click(timeout=5000)

                page.wait_for_timeout(1000)

                qty_after = ""
                for qs in QTY_SELECTORS:
                    try:
                        qel = page.locator(qs).first
                        if qel.count() > 0:
                            qty_after = qel.inner_text(timeout=2000)
                            break
                    except Exception:
                        continue

                content_after = page.content()
                if qty_before != qty_after and qty_before:
                    print(f"  PASS — quantité changée : {qty_before!r} → {qty_after!r}")
                elif content_before != content_after:
                    print(f"  PASS (DOM changé) — le contenu de la page a été mis à jour")
                else:
                    print(f"  FAIL — rien n'a changé après sélection portions")
                    success = False
                    failed_tests.append("Test 3: portions non mises à jour")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 3: {e}")

            # ── Test 4 — Ajout d'une recette ────────────────────────────────
            print("\n[Test 4] Ajout d'une recette...")
            try:
                page.goto(base_url)
                page.wait_for_load_state("networkidle", timeout=10000)
                wait_for_any(page, CARD_SELECTORS + ADD_BTN_SELECTORS, timeout=8000)

                # Cliquer sur le bouton d'ajout
                clicked = False
                for sel in ADD_BTN_SELECTORS:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.click(timeout=5000)
                            clicked = True
                            break
                    except Exception:
                        continue

                if not clicked:
                    raise Exception("Bouton d'ajout introuvable")

                page.wait_for_load_state("networkidle", timeout=10000)

                # Remplir nom
                for sel in ["input[name='name']", "#recipeName", "input[placeholder*='nom']",
                            "input[placeholder*='Nom']", "input[type='text']"]:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.fill("Recette Test Bench")
                            break
                    except Exception:
                        continue

                # Remplir temps (premier input number)
                number_inputs = page.locator("input[type='number']").all()
                if len(number_inputs) >= 1:
                    number_inputs[0].fill("15")
                if len(number_inputs) >= 2:
                    number_inputs[1].fill("2")

                # Remplir TOUS les champs ingrédients existants (le formulaire peut en pré-créer)
                # puis en ajouter un si aucun n'existe
                ING_QTY_SELS  = [".ingredient-qty", "input[placeholder*='Quantité']",
                                  "input[placeholder*='quantité']", ".ingredient-row input[type='number']"]
                ING_UNIT_SELS = [".ingredient-unit", "input[placeholder*='nité']",
                                  "input[placeholder*='Unit']", ".ingredient-row input[type='text']:nth-child(1)"]
                ING_NAME_SELS = [".ingredient-name", "input[placeholder*='Ingrédient']",
                                  "input[placeholder*='ingrédient']", ".ingredient-row input[type='text']:last-child"]

                # Compter les lignes existantes
                existing_rows = 0
                for sel in [".ingredient-row", ".ingredient", "[class*='ingredient-row']"]:
                    c = page.locator(sel).count()
                    if c > 0:
                        existing_rows = c
                        break

                if existing_rows == 0:
                    # Aucune ligne — cliquer sur "Ajouter un ingrédient"
                    for sel in ["button:has-text('Ajouter un ingr')", "button:has-text('Ingrédient')",
                                "button:has-text('ingredient')", "#addIngredient", ".add-ingredient"]:
                        try:
                            el = page.locator(sel).first
                            if el.count() > 0:
                                el.click(timeout=3000)
                                break
                        except Exception:
                            continue

                # Remplir la première ligne (ou toutes)
                for sel in ING_QTY_SELS:
                    try:
                        els = page.locator(sel).all()
                        if els:
                            els[0].fill("200")
                            break
                    except Exception:
                        continue
                for sel in ING_UNIT_SELS:
                    try:
                        els = page.locator(sel).all()
                        if els:
                            els[0].fill("g")
                            break
                    except Exception:
                        continue
                for sel in ING_NAME_SELS:
                    try:
                        els = page.locator(sel).all()
                        if els:
                            els[0].fill("farine")
                            break
                    except Exception:
                        continue

                # Remplir toutes les autres lignes d'ingrédients avec des valeurs non-vides
                for sel in ING_QTY_SELS:
                    try:
                        els = page.locator(sel).all()
                        for el in els[1:]:
                            try: el.fill("1")
                            except Exception: pass
                        break
                    except Exception:
                        continue
                for sel in ING_UNIT_SELS:
                    try:
                        els = page.locator(sel).all()
                        for el in els[1:]:
                            try: el.fill("g")
                            except Exception: pass
                        break
                    except Exception:
                        continue
                for sel in ING_NAME_SELS:
                    try:
                        els = page.locator(sel).all()
                        for el in els[1:]:
                            try: el.fill("ingrédient")
                            except Exception: pass
                        break
                    except Exception:
                        continue

                # Remplir les étapes existantes ou en ajouter une
                step_sels = ["textarea", ".step-desc", "input[placeholder*='étape']",
                             "input[placeholder*='Étape']", ".step-row textarea"]
                existing_steps = 0
                for sel in step_sels:
                    c = page.locator(sel).count()
                    if c > 0:
                        existing_steps = c
                        break

                if existing_steps == 0:
                    for sel in ["button:has-text('Ajouter une étape')", "button:has-text('étape')",
                                "button:has-text('Étape')", "#addStep", ".add-step"]:
                        try:
                            el = page.locator(sel).first
                            if el.count() > 0:
                                el.click(timeout=3000)
                                break
                        except Exception:
                            continue

                for sel in step_sels:
                    try:
                        els = page.locator(sel).all()
                        if els:
                            els[0].fill("Mélanger les ingrédients")
                            break
                    except Exception:
                        continue

                # Soumettre
                for sel in SUBMIT_SELECTORS:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.click(timeout=5000)
                            break
                    except Exception:
                        continue

                page.wait_for_load_state("networkidle", timeout=10000)
                page.wait_for_timeout(1500)

                if "Recette Test Bench" in page.content():
                    print("  PASS — recette créée et visible dans la liste")
                else:
                    print("  FAIL — 'Recette Test Bench' non trouvée après soumission")
                    success = False
                    failed_tests.append("Test 4: recette non visible après ajout")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 4: {e}")

            # ── Test 5 — Persistance après reload ───────────────────────────
            print("\n[Test 5] Persistance après rechargement...")
            try:
                page.goto(base_url)
                page.wait_for_load_state("networkidle", timeout=10000)
                page.wait_for_timeout(1000)
                if "Recette Test Bench" in page.content():
                    print("  PASS — recette persistée après reload")
                else:
                    print("  FAIL — recette disparue après reload")
                    success = False
                    failed_tests.append("Test 5: persistance échouée")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 5: {e}")

            browser.close()

    except Exception as e:
        print(f"ERROR: inattendu — {e}")
        import traceback
        traceback.print_exc()
        success = False
        failed_tests.append(f"Unexpected: {e}")
    finally:
        proc.kill()
        proc.wait()

    print("\n" + "="*50)
    if success:
        print("RESULT: ALL TESTS PASSED")
    else:
        print(f"RESULT: FAILED ({len(failed_tests)} test(s))")
        for t in failed_tests:
            print(f"  - {t}")

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

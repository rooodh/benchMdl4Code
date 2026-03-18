#!/usr/bin/env python3
"""
Validator Playwright pour recipe-book.
Reçoit : workdir port
Retourne : exit 0 (succès) ou exit 1 (échec)
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
        print("Usage: recipe-book.py <workdir> <port>")
        sys.exit(1)

    workdir = sys.argv[1]
    port = int(sys.argv[2])

    # Démarrer l'application
    print(f"Starting app in {workdir} on port {port}...")
    proc = subprocess.Popen(
        ["python", "main.py"],
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

    try:
        import importlib.util
        if importlib.util.find_spec("playwright") is None:
            raise ImportError("playwright")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            base_url = f"http://localhost:{port}"

            # Test 1 — Liste non vide
            print("\n[Test 1] Liste des recettes non vide...")
            page.goto(base_url)
            page.wait_for_load_state("networkidle")
            cards = page.locator(".card, [class*='card'], [class*='recipe']").all()
            # fallback : chercher des liens ou items qui ressemblent à des recettes
            if len(cards) == 0:
                # essai plus large
                cards = page.locator("li, article, .item").all()
            if len(cards) >= 1:
                print(f"  PASS — {len(cards)} recette(s) affichée(s)")
            else:
                print("  FAIL — aucune recette trouvée dans la liste")
                success = False
                failed_tests.append("Test 1: liste vide")

            # Test 2 — Navigation vers le détail
            print("\n[Test 2] Navigation vers le détail...")
            try:
                # Cliquer sur le premier élément cliquable ressemblant à une recette
                first = page.locator("a[href*='recipe'], .card, article, li").first
                first.click()
                page.wait_for_load_state("networkidle")
                # Vérifier présence d'ingrédients
                has_ingredients = page.locator(
                    "[class*='ingredient'], li, ul"
                ).count() > 0
                has_steps = page.locator(
                    "[class*='step'], ol, [class*='instruction']"
                ).count() > 0
                if has_ingredients and has_steps:
                    print("  PASS — ingrédients et étapes présents")
                else:
                    print(f"  FAIL — ingrédients={has_ingredients}, étapes={has_steps}")
                    success = False
                    failed_tests.append("Test 2: détail incomplet")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 2: {e}")

            # Test 3 — Ajustement des portions
            print("\n[Test 3] Ajustement des portions...")
            try:
                # Récupérer une quantité avant
                qty_before = page.locator("[class*='quantity'], [class*='amount'], td, li").first.inner_text()
                # Chercher le sélecteur x2
                x2 = page.locator("button:has-text('x2'), [data-multiplier='2'], select").first
                x2.click()
                page.wait_for_timeout(500)
                qty_after = page.locator("[class*='quantity'], [class*='amount'], td, li").first.inner_text()
                if qty_before != qty_after:
                    print(f"  PASS — quantité changée : {qty_before!r} → {qty_after!r}")
                else:
                    print(f"  FAIL — quantité inchangée après x2 ({qty_before!r})")
                    success = False
                    failed_tests.append("Test 3: portions non mises à jour")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 3: {e}")

            # Test 4 — Ajout d'une recette
            print("\n[Test 4] Ajout d'une recette...")
            try:
                page.goto(base_url)
                page.wait_for_load_state("networkidle")
                # Chercher le bouton d'ajout
                add_btn = page.locator("button:has-text('Ajouter'), a:has-text('Ajouter'), [href*='add'], [href*='new']").first
                add_btn.click()
                page.wait_for_load_state("networkidle")

                # Remplir le formulaire
                page.locator("input[name='name'], input[placeholder*='nom'], input[type='text']").first.fill("Recette Test Bench")
                page.locator("input[name='prep_time'], input[type='number']").first.fill("15")
                servings_inputs = page.locator("input[name='servings'], input[type='number']").all()
                if len(servings_inputs) >= 2:
                    servings_inputs[1].fill("2")

                # Ajouter un ingrédient
                add_ing = page.locator("button:has-text('Ajouter un ingr'), button:has-text('ingredient'), button:has-text('Ingrédient')").first
                add_ing.click()
                ing_inputs = page.locator("input[placeholder*='quantité'], input[placeholder*='quantity'], input[type='number']").all()
                if ing_inputs:
                    ing_inputs[-1].fill("200")
                unit_inputs = page.locator("input[placeholder*='unité'], input[placeholder*='unit']").all()
                if unit_inputs:
                    unit_inputs[-1].fill("g")
                ing_name_inputs = page.locator("input[placeholder*='ingrédient'], input[placeholder*='nom']").all()
                if ing_name_inputs:
                    ing_name_inputs[-1].fill("farine")

                # Ajouter une étape
                add_step = page.locator("button:has-text('Ajouter une étape'), button:has-text('étape'), button:has-text('step')").first
                add_step.click()
                step_inputs = page.locator("textarea").all()
                if step_inputs:
                    step_inputs[-1].fill("Mélanger les ingrédients")

                # Soumettre
                page.locator("button[type='submit'], button:has-text('Enregistrer'), button:has-text('Sauvegarder')").first.click()
                page.wait_for_load_state("networkidle")

                # Vérifier que la recette apparaît
                content = page.content()
                if "Recette Test Bench" in content:
                    print("  PASS — recette créée et visible dans la liste")
                else:
                    print("  FAIL — 'Recette Test Bench' non trouvée après soumission")
                    success = False
                    failed_tests.append("Test 4: recette non visible après ajout")
            except Exception as e:
                print(f"  FAIL — {e}")
                success = False
                failed_tests.append(f"Test 4: {e}")

            # Test 5 — Persistance après reload
            print("\n[Test 5] Persistance après rechargement...")
            try:
                page.goto(base_url)
                page.wait_for_load_state("networkidle")
                content = page.content()
                if "Recette Test Bench" in content:
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

    except ImportError:
        print("ERROR: playwright not installed.")
        print("Fix: pip install playwright && playwright install chromium")
        proc.kill()
        sys.exit(2)  # exit 2 = env problem, not model failure
    except Exception as e:
        print(f"ERROR: unexpected — {e}")
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

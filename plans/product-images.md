# Implementation Plan: The ThoughtTronix Store — Product Images

*Companion to `prd/product-images.md`. The PRD owns the requirements; this plan owns the sequence. Where a task says "per the PRD," the PRD's wording is authoritative. Do not improvise alternatives. The suite must be green at every phase boundary.*

---

## Phase 0 — Branch Setup

**Goal:** Work starts from a `main` that contains both the finished coupons feature and marketing's imagery.

**Tasks:**
1. Merge `feature/seasonal-coupons` into `main` via a GitHub pull request.
2. Pull `main` locally; confirm `product-images/` is present (13 PNGs) and that the stray `images1` file is gone.
3. Create `feature/product-images` from the updated `main`. Bring along (and commit first) `prd/product-images.md` and this plan.

**Verification.** *Automated:* `uv run pytest` green on the new branch before any change. *Manual:* `git log` shows the coupons commits and the image upload commits on the branch.

**Out of bounds:** any code change.

---

## Phase 1 — Tracer Bullet: One Image, Every Layer

**Goal:** A product with an image shows it on the catalog and detail pages; a product without one, or whose file has vanished, shows its placeholder. This proves the first non-negotiable end to end before any upload exists.

**Tasks:**
1. Add Pillow with `uv add pillow`.
2. Settings: `MEDIA_URL = "media/"` and `MEDIA_ROOT = BASE_DIR / "media"`, with working defaults (no `.env` needed). Add `media/` to `.gitignore`.
3. `config/urls.py`: serve media with `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` when `DEBUG` is on, per the PRD.
4. `Product.image`: an optional `ImageField` with an `upload_to` function producing `products/<slug>-<random suffix>.webp`. Generate and run the migration.
5. `Product.display_image_url`: the media URL only when the field is set **and** `image.storage.exists(image.name)`; otherwise the category placeholder's static URL. Docstring explains it is the single enforcement point of the display rule.
6. Catalog and detail templates: swap `{% static product.category.placeholder_image %}` for `product.display_image_url`. Put the image inside a fixed 4:3 frame (`aspect-[4/3]`, `object-contain`, `w-full h-full`, background matching the card) and add `loading="lazy"`.
7. `conftest.py`: a `media_root` fixture that points `MEDIA_ROOT` at `tmp_path` via the `settings` fixture, plus a helper fixture that builds a small in-memory PNG with Pillow.

**Verification.** *Automated:* `display_image_url` covering no image (placeholder), image present (media URL), and image set but file deleted (placeholder); catalog and detail render the right `src` in each case. *Manual:* in `manage.py shell`, attach one of marketing's PNGs to Seraphine; see it in the catalog, uncropped, inside a 4:3 frame; delete the file from `media/` and reload: placeholder, no broken icon.

**Out of bounds:** validation, resizing, uploads, the seed. The image in this phase is attached by hand.

---

## Phase 2 — The Gatekeeper: `products/images.py`

**Goal:** One function decides whether a file is usable and turns it into the stored WebP. This is the core of the second non-negotiable.

**Tasks:**
1. Create `products/images.py` with a public function (docstring and type hints) that takes an uploaded or opened file and its display name, and returns a processed WebP `ContentFile` or raises a validation error.
2. Checks in order, per the PRD: size ≤ 5 MB → Pillow can open it → detected format in {PNG, JPEG, WebP} → dimensions ≥ 600×600 and ≤ 8000 per side. Dimensions are read from the header before any full decode.
3. Processing: resize so the longest side is ≤ 1600 px (keeping the aspect ratio; never upscale), and save as WebP, keeping transparency. Any exception during processing becomes the "couldn't prepare" error.
4. Error messages copied **verbatim** from the PRD's table, filled in with the file's name and real numbers (MB to one decimal, pixels as `W × H`, format name in capitals).

**Verification.** *Automated:* one test per rule, asserting the exact message: oversize; a text file; a TIFF renamed to `.png`; 150×120; 9000×100; a forced processing failure. Accepted PNG, JPEG, and WebP inputs produce WebP output with longest side ≤ 1600; a transparent PNG keeps its alpha channel; a 700×700 input is not upscaled. *Manual:* run the function in the shell against every file in `product-images/`; all pass.

**Out of bounds:** forms, views, templates. This phase is a pure module and its tests.

---

## Phase 3 — The Back-Office Image Card

**Goal:** Employees upload, replace, and remove a product's image from its edit page. Rejections are explained in plain language, and no good file is ever lost.

**Tasks:**
1. `ProductImageForm`: a single required image field whose `clean` calls `products/images.py` and swaps in the processed file. `ProductForm` is unchanged (it does not include `image`).
2. Two staff-only views on pk URLs, both named in the `products` namespace: upload/replace (POST) and remove (POST). Each returns the partial.
3. File lifecycle, per the PRD: save the new state first, then delete the old file in `transaction.on_commit`. Remove clears the field and deletes the file on commit. A product delete also removes its file on commit. A rejected upload changes nothing.
4. Partial `templates/products/partials/_product_image.html`: a preview using `display_image_url`, a file input, Upload/Replace and Remove buttons, and errors under the input. The form uses `hx-encoding="multipart/form-data"` and swaps only itself. Remove uses `hx-confirm="Remove this image?"`.
5. `manage_product_form.html`: include the card below the details form when editing. When creating, show the "Save the product first, then add its image here." note instead.
6. `ManageProductCreateView` redirects to the new product's edit page.
7. `ProductAdmin`: `image` is read-only.

**Verification.** *Automated:* each view is staff-only (302/403 otherwise); a successful upload returns the partial with the new preview; a rejected upload returns the partial with the PRD message and leaves the existing image and its file untouched; replace deletes the old file only after commit (`django_capture_on_commit_callbacks`); remove clears the field and file; product delete removes the file; create redirects to edit; `image` is in `ProductAdmin.readonly_fields`. *Manual:* as `employee`, type a new tagline without saving, upload an image, and confirm the tagline is still there; try a PDF, a tiny PNG, and a TIFF and read each message; replace an image and confirm the old file is gone from `media/products/`; remove it and see the placeholder.

**Out of bounds:** the product list thumbnail and the seed.

---

## Phase 4 — Back-Office List Thumbnails

**Goal:** Employees can see at a glance which products still need imagery.

**Tasks:**
1. `manage_products.html`: a small 4:3 `object-contain` thumbnail per row using `display_image_url`, with `loading="lazy"`.

**Verification.** *Automated:* the list renders the media URL for a product with an image and the placeholder for one without, or whose file is missing. *Manual:* as `employee`, scan the list and spot the placeholder rows.

**Out of bounds:** cart, checkout, and order pages, which are out of scope per the PRD.

---

## Phase 5 — Seeding Marketing's Imagery

**Goal:** `manage.py seed` builds a demo world with real images, produced by the same path as employee uploads.

**Tasks:**
1. In `seed.py`, a readable module-level map from filename to product slug, copied from the PRD's table (12 entries; `SyncRest GPT Text.png` deliberately absent, with a comment explaining why).
2. Empty `media/products/` before rebuilding, alongside the existing data wipe.
3. Attach each mapped file through `products/images.py`. If a file fails, stop with a `CommandError` naming the file and the rule it broke. A mapped file missing from `product-images/` also stops the seed, with its name.
4. The success summary line reports how many products got images.

**Verification.** *Automated:* the existing seed tests stay green (the seed is not invoked by new tests, per CLAUDE.md). *Manual:* run `seed` twice and confirm `media/products/` holds exactly 12 `.webp` files each time; browse the catalog: 12 real images, 22 placeholders, none cropped, no broken icons; check that the catalog page weight is a few MB, not ~22 MB.

**Out of bounds:** changing marketing's files in `product-images/`.

---

## Phase 6 — Documentation and Polish

**Goal:** The repository describes the feature as built.

**Tasks:**
1. `CLAUDE.md`: note `products/images.py` as the single gatekeeper for product images, `Product.display_image_url` as the only way templates show a product image, `media/` (gitignored, generated by the seed and uploads), `product-images/` (marketing's source files), and the DEBUG-only media serving.
2. README: mention that the seed loads product imagery, and that media serving under `DEBUG=False` is not yet configured.
3. Append a PROMPTS.md entry for this session (append only; never rewrite earlier entries).
4. Full `ruff check`, `ruff format`, and `pytest` pass.

**Verification.** *Automated:* full suite green, Ruff clean, CI passes. *Manual:* a fresh clone, README steps only, then seed and browse: real images appear.

**Out of bounds:** nothing new. This phase adds no features.

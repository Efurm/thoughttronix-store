# PRD: The ThoughtTronix Store — Product Images

*Commissioned by ThoughtTronix Marketing. "Your Thoughts, Our Business."*

---

## Problem Statement

The catalog sells the most intimate consumer technology on the market using clip-art. Every product, from the Seraphine Home Hub to the SoulSear Mark II, is represented by one of seven category placeholders. Marketing has produced real product imagery and would like customers to see it, ideally before purchase.

Marketing has set two conditions, and neither is negotiable:

1. **Every product displays either its uploaded image, when one is available, or the existing placeholder.** Missing files and broken image icons are not part of the approved visual identity.
2. **Employees upload product images through the back office.** When an employee provides a file the site cannot use, the site rejects it and explains the problem in plain language. The site never accepts a file and then loses it.

The imagery lives in the repository in `product-images/` (13 PNGs, 1.7–2.5 MB each, mostly 1122×1402 portrait).

## Solution

Each product gains one optional image. The storefront shows the image when its file is actually present, and the category placeholder otherwise. That decision is made in exactly one place on the server, before any HTML reaches the browser.

Employees manage the image from a dedicated card on the product's back-office edit page. The card is its own single-field HTMX form, so an upload has exactly two outcomes: **saved**, or **rejected with a plain-language reason**. No unrelated field can cause a good file to be dropped. Accepted files are resized to a web-friendly WebP before being stored, so the catalog stays fast.

The seed command loads marketing's imagery through the same validate-and-resize path that employee uploads use, so the demo world is a faithful preview of production behavior.

## User Stories

**Visitor / customer**

1. As a visitor, I see each product's real image in the catalog grid and on its detail page when one has been uploaded.
2. As a visitor, I see the product's category placeholder when it has no image, and also when its image file has gone missing on the server. I never see a broken image icon.
3. As a visitor, every catalog card's image area has the same 4:3 shape, and I always see the whole image. Nothing is cropped (including text that marketing baked into an image).
4. As a visitor, the catalog loads quickly. Images are web-sized and load lazily as I scroll.

**Employee (staff)**

5. As an employee, after creating a product I land on its edit page, where an image card invites me to add its image.
6. As an employee, I can upload an image for a product from its edit page without reloading the page. Any unsaved edits in the product details form are left untouched.
7. As an employee, I can replace a product's image. The old image stays in place until the new one is safely saved.
8. As an employee, I can remove a product's image (after confirming), returning the product to its placeholder.
9. As an employee, when I upload a file the site cannot use, I am told exactly what is wrong with *that* file, with its real numbers, and what to do instead. The product's current image is unaffected.
10. As an employee, I can see a thumbnail of each product's image (or its placeholder) in the back-office product list, so I can spot products still waiting for imagery.

**Admin**

11. As an admin, I can see in the Django admin whether a product has an image, but uploads happen only in the back office, so the upload rules cannot be bypassed.

**Developer**

12. As a developer, `manage.py seed` gives the demo world marketing's real imagery, resized exactly as an employee upload would be, and stops with a clear message if any file in `product-images/` breaks the upload rules.

## Implementation Decisions

**Branching.** The seasonal coupons feature merges into `main` first. This work happens on `feature/product-images`, created from the updated `main` (which already contains `product-images/`).

**Data model.** `Product.image`: an optional `ImageField` (one image per product, no gallery). Adds Pillow as a dependency. Files live on disk under `MEDIA_ROOT` (`media/`, gitignored, the same as compiled CSS).

**The display rule.** `Product.display_image_url` returns the uploaded image's URL **only if** the field is set **and** the file exists in storage. Otherwise it returns the category placeholder's static URL. Every template that shows a product image uses only this property. This is the single enforcement point of the first non-negotiable.

**Where images appear.** The catalog grid, the product detail page, the back-office edit-page image card, and thumbnails in the back-office product list. Cart, checkout, and order pages are out of scope (past orders would raise a separate "which image did they buy?" question).

**Display shape.** A fixed 4:3 frame using `object-contain`. The image is never cropped, and any letterbox bands take the card's background color. Placeholders (400×300) fit the frame exactly. Because any shape displays correctly, uploads are not rejected for their aspect ratio. Images carry `loading="lazy"`. Alt text remains the product name.

**What counts as usable.** Checks run cheapest first, and the employee sees the first problem found:

1. File size at most **5 MB**.
2. Pillow can open it as an image.
3. Its *detected* format (not its extension) is **PNG, JPEG, or WebP**. These three always render in browsers; TIFF, BMP, and similar formats are rejected. SVG is excluded (Django's `ImageField` rejects it, and uploaded SVG is a script-injection risk).
4. Dimensions at least **600 × 600** pixels and at most **8000** pixels on each side. The maximum keeps "pixel bombs" out with our own message rather than Pillow's.

**Processing.** After validation, the image is resized so its longest side is at most **1600 px** and saved as **WebP** (which preserves transparency). Only this processed file is stored; employee originals are not archived. If processing fails for any reason, the upload is rejected with a plain message and nothing is saved.

**One path in.** `products/images.py` holds the single validate-and-resize function. The back-office image form calls it and turns failures into form errors (forms own their validation); the seed calls it and turns failures into a stopping error. In the Django admin, `image` is read-only.

**File naming.** `upload_to` produces `products/<slug>-<random suffix>.webp`. Public URLs are tidy and traceable, and a fresh suffix on every upload means browsers never show a stale cached image. Later slug changes do not rename existing files.

**File lifecycle.** On replace or remove, the new state is saved first. The old file is deleted only after the transaction commits (`transaction.on_commit`), so at every moment the product points at a file that exists. Deleting a product deletes its image file the same way. Media folders never accumulate orphaned files.

**The image form.** A separate single-field form, rendered as an HTMX partial `templates/products/partials/_product_image.html` on the product edit page. It uses `multipart/form-data` encoding and swaps only itself on upload and remove. Remove uses `hx-confirm` ("Remove this image?"). On the new-product page the card reads *"Save the product first, then add its image here,"* and creating a product redirects to its edit page.

**Rejection messages.** Each message names the file, gives its real numbers, and says what to do:

| Situation | Message |
|---|---|
| No file chosen | Choose an image file to upload. |
| Over 5 MB | "photo.png" is 7.3 MB. The largest image we can accept is 5 MB. Try exporting a smaller version. |
| Not an image, or damaged | "report.pdf" isn't an image we can open. Upload a PNG, JPEG, or WebP picture. |
| Image in another format | "scan.tiff" is a TIFF image. We accept PNG, JPEG, or WebP. Save it in one of those formats and try again. |
| Too small | "logo.png" is 150 × 120 pixels. Images need to be at least 600 pixels wide and 600 pixels tall so they look sharp in the store. |
| Too large in pixels | "poster.png" is 12000 × 9000 pixels. Images can be at most 8000 pixels on each side. |
| Processing failed | We couldn't prepare "photo.png" for the store. Try saving it again as a PNG or JPEG and uploading that copy. Your current image hasn't changed. |

**Serving media.** `config/urls.py` serves `MEDIA_URL` with Django's `static()` helper when `DEBUG` is on, mirroring how static files are served today. **Serving media (and static files) under `DEBUG=False` is out of scope**; a future deployment task must cover both. Settings gain `MEDIA_URL` and `MEDIA_ROOT` with working defaults (no `.env` required).

**Seed data.** `product-images/` stays the source of truth, exactly as marketing delivered it. `seed.py` holds an explicit filename → product slug map, empties `media/products/` before rebuilding, and attaches each file through `products/images.py`:

| File | Product |
|---|---|
| Calm Collar GPT Man.png | `calm-collar` |
| CrowdCalm Array No Text.png | `crowdcalm-array` |
| DreamWeaver Matrix GPT 3.png | `dreamweaver` |
| Hush GPT No Text.png | `hush` |
| MindSync Duo.png | `mindsync-duo` |
| MindSync GPT 2.png | `mindsync` |
| MoodSet GPT No Text.png | `moodset` |
| RecallPro.png | `recallpro` |
| Seraphine GPT Text.png | `seraphine` |
| SoulSear No Text.png | `soulsear-mark-ii` |
| SyncRest GPT No Text.png | `syncrest` |
| Veil GPT Text.png | `veil` |

`SyncRest GPT Text.png` (the full advertisement layout) is kept in the folder but not seeded: its fine print is unreadable at card size, and the page already prints the name and copy. The remaining products keep their placeholders.

This supersedes the core-platform PRD's statement that `Product` carries no image field.

## Testing Decisions

pytest + pytest-django, plain fixtures in `conftest.py`. A fixture points `MEDIA_ROOT` at a temporary directory, so tests never touch the real `media/` or `product-images/`. Test images are generated in memory with Pillow. Tests never invoke the seed command.

Coverage priorities, in order:

1. **`products/images.py`.** Each rejection rule fires with its exact message: oversize, not an image, wrong detected format (including a TIFF renamed to `.png`), too small, too large. Valid PNG, JPEG, and WebP inputs are accepted; output is WebP with its longest side at most 1600 px; transparency survives.
2. **`Product.display_image_url`.** No image gives the placeholder; image present gives the media URL; image set but file deleted gives the placeholder.
3. **File lifecycle.** Replace keeps the new file and deletes the old one only after commit; a rejected replacement leaves the current image and file untouched; remove clears the field and deletes the file; deleting a product deletes its file.
4. **The image form and views.** Staff-only access; HTMX upload returns the partial with a preview on success, or the error message on rejection; remove works; product create redirects to the edit page.
5. **Templates.** The catalog, detail, and back-office list render the uploaded image or the placeholder as appropriate, never a media URL for a missing file.
6. **Admin.** `image` is read-only in `ProductAdmin`.

## Changes Made During the Build

Small departures from the decisions above, each found while building and testing:

- **Lazy loading** is on catalog cards and back-office thumbnails, but not on the product detail page, whose single image is the first thing on screen.
- **Absurdly large images** (over Pillow's ~179-megapixel safety limit) cannot have their dimensions read, so they get *"… is far too large in pixels. Images can be at most 8000 pixels on each side."* rather than the exact `W × H` message.
- **Damaged files** are caught when their pixels are decoded and get the "isn't an image we can open" message.
- **MPO**, the JPEG variant many phone cameras write, is accepted as JPEG.

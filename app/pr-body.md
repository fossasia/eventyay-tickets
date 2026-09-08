This PR implements an AJAX-based inline email preview for the Message Center compose workflows, replacing the previous full-page reload behavior.

### Changes Made:
1. **Backend Adjustments**:
   - Modified `ComposeMailBaseView` (Talks), `SenderView` (Tickets), `ComposeTeamsMail` (Teams), and `EditEmailQueueView` (Outbox) to handle `action=preview` requests via AJAX.
   - For preview requests, relaxed HTML5 form validation and Django form required validation (`draft_save=True` logic and `.required = False`) on fields like `subject` and `message` so a preview can be generated even if the user hasn't filled out all fields or selected recipients.
   - Refactored the preview rendering to return a JSON response containing the generated HTML for the preview.
   - Included `mail_count` and `preview_warning` in the view context to appropriately show the "Preview generated with sample recipient data" banner when no recipients are selected.

2. **Frontend UI/JS Adaptations**:
   - Created `mail-preview.js` to intercept clicks on the "Preview email" buttons, preventing default form submission.
   - Replaced default form submission with a `fetch()` request sending `FormData` via AJAX.
   - Display a loading spinner within the preview container while the request is processing.
   - Fixed the "bouncing cursor" bug by applying `formnovalidate` and `data-no-loading` attributes to the Preview buttons. This prevents the browser from validating empty fields and prevents Eventyay's global `formTools.js` from hijacking the button click.
   - Added `e.stopImmediatePropagation()` to ensure global listeners do not attach loading states inappropriately.
   - Fixed UI layout anomalies for Tickets vs Talks by wrapping the loading spinner contents inside an inner `<div>`, ensuring `tickets_email.css` flexbox layout (`.alert > * { flex: 1 1 auto; }`) doesn't stretch the spinner icon across the page.

### Why:
Clicking the "Preview email" button previously submitted the entire form to the server and reloaded the page. This broke the user experience, particularly around maintaining form state, recipient selections, and the action bar's position. This inline, AJAX-based approach ensures that users can continuously preview email templates smoothly without losing context or their place on the page.

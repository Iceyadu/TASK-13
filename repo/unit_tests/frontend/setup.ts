/**
 * Vitest setup file for the HarborView frontend tests.
 *
 * This file is referenced by vitest.config.ts via the `setupFiles` option.
 */

import { afterEach } from "vitest";

// Clean up the DOM after every test so components don't leak between tests.
afterEach(() => {
  document.body.innerHTML = "";
});

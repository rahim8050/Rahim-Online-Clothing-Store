*** a/Rahim_Online_ClothesStore/settings.py
--- b/Rahim_Online_ClothesStore/settings.py
@@
-from pathlib import Path
+from pathlib import Path
+import sys
@@
 BASE_DIR = Path(__file__).resolve().parent.parent
@@
-# Static files (CSS, JavaScript, Images)
-# https://docs.djangoproject.com/en/5.0/howto/static-files/
-STATIC_URL = "static/"
+# Static files (CSS, JavaScript, Images)
+# WhiteNoise + collectstatic compatible
+STATIC_URL = "/static/"
+STATIC_ROOT = BASE_DIR / "staticfiles"
+STATICFILES_DIRS = [BASE_DIR / "static"]
+STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
@@
-# Stripe (existing code probably enforced envs here)
-# raise RuntimeError(...) if missing
+from environ import Env
+env = Env()
+
+# Guard Stripe envs so build-time commands don't crash, but prod runtime does.
+STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
+STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)
+
+MGMT_CMDS_SAFE = {"collectstatic", "migrate", "makemigrations", "check", "test", "shell"}
+RUNNING_MGMT = len(sys.argv) > 1 and sys.argv[1] in MGMT_CMDS_SAFE
+REQUIRE_PAYMENT_ENVS = (not env.bool("DEBUG", False)) and not RUNNING_MGMT
+
+if REQUIRE_PAYMENT_ENVS:
+    _missing = [k for k, v in {
+        "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
+        "STRIPE_WEBHOOK_SECRET": STRIPE_WEBHOOK_SECRET,
+    }.items() if not v]
+    if _missing:
+        raise RuntimeError(f"Missing required payment envs: {', '.join(_missing)}")
+else:
+    STRIPE_SECRET_KEY = STRIPE_SECRET_KEY or "disabled"
+    STRIPE_WEBHOOK_SECRET = STRIPE_WEBHOOK_SECRET or "disabled"
*** /dev/null
--- b/tailwind.config.js
@@
+module.exports = {
+  content: [
+    "./templates/**/*.{html,htm}",
+    "./**/*.html",
+    "./**/*.{js,ts,vue}",
+    "./**/*.py"
+  ],
+  theme: { extend: {} },
+  plugins: [],
+};
*** /dev/null
--- b/src/input.css
@@
+@tailwind base;
+@tailwind components;
+@tailwind utilities;
+
+/* put any custom CSS below */
*** a/templates/base.html
--- b/templates/base.html
@@
-{% load static %}
-<!-- Tailwind CDN (remove in production): -->
-<script src="https://cdn.tailwindcss.com"></script>
-<link rel="stylesheet" href="{% static 'src/input.css' %}">
+{% load static %}
+<link rel="stylesheet" href="{% static 'build/tailwind.css' %}">

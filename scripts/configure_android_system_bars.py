from pathlib import Path
import re

candidates = list(Path("android/app/src/main/java").rglob("MainActivity.java"))
if len(candidates) != 1:
    raise SystemExit(f"Expected one generated MainActivity.java, found {len(candidates)}")

path = candidates[0]
original = path.read_text(encoding="utf-8")
match = re.search(r"^package\s+([\w.]+);", original, re.M)
if not match:
    raise SystemExit("Could not resolve Android application package")
package = match.group(1)

text = f'''package {package};

import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);

        Window window = getWindow();
        window.setStatusBarColor(Color.WHITE);
        window.setNavigationBarColor(Color.WHITE);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {{
            window.setNavigationBarContrastEnforced(false);
        }}

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
            window.setDecorFitsSystemWindows(false);
            WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {{
                int appearance = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                        | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                controller.setSystemBarsAppearance(appearance, appearance);
            }}

            View content = findViewById(android.R.id.content);
            content.setOnApplyWindowInsetsListener((view, insets) -> {{
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return insets;
            }});
            content.requestApplyInsets();
        }} else {{
            int flags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {{
                flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            }}
            window.getDecorView().setSystemUiVisibility(flags);
        }}
    }}
}}
'''

path.write_text(text, encoding="utf-8")
print(f"Applied native system-bar inset handling to {path}")

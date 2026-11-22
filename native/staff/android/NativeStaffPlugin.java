package NATIVE_STAFF_PACKAGE;

import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.*;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.LinkedHashMap;
import java.util.Map;

@CapacitorPlugin(name = "NativeStaff")
public final class NativeStaffPlugin extends Plugin {
    private static final int PAPER = Color.rgb(248,246,241);
    private static final int CARD = Color.rgb(255,253,250);
    private static final int INK = Color.rgb(23,41,35);
    private static final int GREEN = Color.rgb(35,71,59);
    private static final int MUTED = Color.rgb(84,94,85);
    private Dialog dialog;
    private final Map<String, EditText> edits = new LinkedHashMap<>();
    private final Map<String, Spinner> selects = new LinkedHashMap<>();
    private final Map<String, String[]> optionValues = new LinkedHashMap<>();

    private int dp(float n) { return (int)(n * getContext().getResources().getDisplayMetrics().density + .5f); }
    private GradientDrawable background(int color, int radius) {
        GradientDrawable bg = new GradientDrawable(); bg.setColor(color); bg.setCornerRadius(dp(radius)); return bg;
    }
    private LinearLayout column() {
        LinearLayout v = new LinearLayout(getContext()); v.setOrientation(LinearLayout.VERTICAL); return v;
    }
    private LinearLayout row() {
        LinearLayout v = new LinearLayout(getContext()); v.setOrientation(LinearLayout.HORIZONTAL); v.setGravity(Gravity.CENTER_VERTICAL); return v;
    }
    private TextView text(String s, int sp, int color, boolean bold) {
        TextView v = new TextView(getContext()); v.setText(s); v.setTextSize(sp); v.setTextColor(color);
        if (bold) v.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return v;
    }
    private Button button(String label, String id, boolean primary) {
        Button v = new Button(getContext()); v.setText(label); v.setAllCaps(false);
        v.setTextColor(primary ? Color.WHITE : GREEN); v.setMinHeight(dp(48)); v.setMinimumHeight(dp(48));
        v.setBackground(background(primary ? GREEN : CARD, 12)); v.setOnClickListener(x -> action(id)); return v;
    }
    private void action(String id) {
        if (id.isEmpty()) return;
        JSObject values = new JSObject();
        for (Map.Entry<String,EditText> entry : edits.entrySet()) values.put(entry.getKey(), entry.getValue().getText().toString());
        for (Map.Entry<String,Spinner> entry : selects.entrySet()) {
            int i = entry.getValue().getSelectedItemPosition();
            String[] items = optionValues.get(entry.getKey());
            if (items != null && i >= 0 && i < items.length) values.put(entry.getKey(), items[i]);
        }
        JSObject event = new JSObject(); event.put("id", id); event.put("values", values);
        notifyListeners("action", event);
    }
    private void add(LinearLayout layout, View view, int margin) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1,-2);
        p.bottomMargin = dp(margin); layout.addView(view,p);
    }
    private void weight(LinearLayout layout, View view) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0,-2,1); p.setMargins(dp(2),0,dp(2),0); layout.addView(view,p);
    }
    private JSONArray list(JSONObject s, String key) {
        JSONArray a = s.optJSONArray(key); return a == null ? new JSONArray() : a;
    }
    private void draw(JSONObject s) {
        edits.clear(); selects.clear(); optionValues.clear();
        LinearLayout root = column(); root.setBackgroundColor(PAPER);
        root.setPadding(dp(14),dp(12),dp(14),dp(8));
        LinearLayout header = row();
        weight(header, button("‹", "back", false));
        TextView brand = text("A+ ESTHETIC",14,GREEN,true); brand.setGravity(Gravity.CENTER);
        header.addView(brand,new LinearLayout.LayoutParams(0,-2,3));
        weight(header,button("⌂", "home", false)); add(root,header,12);
        TextView title = text(s.optString("title"),32,INK,false); title.setTypeface(Typeface.SERIF);
        add(root,title,5); add(root,text(s.optString("subtitle"),14,MUTED,false),12);
        JSONArray week = list(s,"week");
        if (week.length() > 0) {
            LinearLayout strip = new LinearLayout(getContext()) {
                private float downX, downY;
                @Override public boolean onInterceptTouchEvent(android.view.MotionEvent e) {
                    if(e.getActionMasked()==android.view.MotionEvent.ACTION_DOWN){downX=e.getX();downY=e.getY();}
                    if(e.getActionMasked()==android.view.MotionEvent.ACTION_MOVE){
                        float dx=e.getX()-downX, dy=e.getY()-downY;
                        if(Math.abs(dx)>dp(15)&&Math.abs(dx)>Math.abs(dy)*1.3f)return true;
                    }
                    return super.onInterceptTouchEvent(e);
                }
                @Override public boolean onTouchEvent(android.view.MotionEvent e){
                    if(e.getActionMasked()==android.view.MotionEvent.ACTION_UP){
                        float delta=e.getX()-downX;
                        if(Math.abs(delta)>dp(35))action(delta<0?"week-next":"week-prev");
                    }
                    return true;
                }
            };
            strip.setOrientation(LinearLayout.HORIZONTAL);
            for(int i=0;i<week.length();i++){
                JSONObject item=week.optJSONObject(i); if(item==null)continue;
                Button cell=button(item.optString("label"), item.optString("id"),item.optBoolean("selected"));
                cell.setTextSize(11); cell.setPadding(0,0,0,0); weight(strip,cell);
            }
            add(root,strip,12);
        }
        ScrollView scroll = new ScrollView(getContext()); scroll.setFillViewport(true);
        LinearLayout body=column(); body.setPadding(0,0,0,dp(12)); scroll.addView(body);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        if(s.optBoolean("busy")) { ProgressBar progress=new ProgressBar(getContext()); add(body,progress,8); }
        if(!s.optString("message").isEmpty()) {
            TextView msg=text(s.optString("message"),15,INK,false); msg.setPadding(dp(14),dp(14),dp(14),dp(14));
            msg.setBackground(background(CARD,12));add(body,msg,10);
        }
        JSONArray fields=list(s,"fields");
        for(int i=0;i<fields.length();i++){
            JSONObject f=fields.optJSONObject(i);if(f==null)continue;
            String key=f.optString("id"); LinearLayout container=column(); container.setPadding(dp(14),dp(10),dp(14),dp(10));container.setBackground(background(CARD,12));
            add(container,text(f.optString("label"),13,INK,true),4);
            JSONArray options=f.optJSONArray("options");
            if(options!=null&&options.length()>0){
                String[] labels=new String[options.length()], vals=new String[options.length()];int choice=0;
                for(int j=0;j<options.length();j++){JSONObject opt=options.optJSONObject(j);labels[j]=opt.optString("label");vals[j]=opt.optString("value");if(vals[j].equals(f.optString("value")))choice=j;}
                Spinner picker=new Spinner(getContext()); ArrayAdapter<String> adapter=new ArrayAdapter<>(getContext(),android.R.layout.simple_spinner_dropdown_item,labels);
                picker.setAdapter(adapter);picker.setSelection(choice); add(container,picker,0);selects.put(key,picker);optionValues.put(key,vals);
            } else {
                EditText input=new EditText(getContext());input.setText(f.optString("value"));input.setTextColor(INK);input.setTextSize(16);
                input.setSingleLine(true);input.setMinHeight(dp(48));input.setHint(f.optString("label"));add(container,input,0);edits.put(key,input);
            }
            add(body,container,10);
        }
        JSONArray rows=list(s,"rows");
        for(int i=0;i<rows.length();i++){
            JSONObject item=rows.optJSONObject(i);if(item==null)continue;
            LinearLayout box=column();box.setPadding(dp(16),dp(14),dp(16),dp(14));box.setBackground(background(CARD,14));
            add(box,text(item.optString("label"),17,INK,true),4);add(box,text(item.optString("detail"),14,MUTED,false),0);
            String id=item.optString("id");if(!id.isEmpty()){box.setOnClickListener(x->action(id));box.setFocusable(true);}
            add(body,box,10);
        }
        JSONArray actions=list(s,"actions");
        for(int i=0;i<actions.length();i++){JSONObject item=actions.optJSONObject(i);if(item!=null)add(body,button(item.optString("label"),item.optString("id"),true),10);}
        JSONArray tabs=list(s,"tabs"); LinearLayout nav=row();
        for(int i=0;i<tabs.length();i++){JSONObject item=tabs.optJSONObject(i);if(item!=null)weight(nav,button(item.optString("label"),item.optString("id"),false));}
        add(root,nav,0);dialog.setContentView(root);
    }
    @PluginMethod public void present(PluginCall call) {
        getActivity().runOnUiThread(()->{
            if(dialog!=null){call.reject("Native screen already active");return;}
            JSObject screen=call.getObject("screen");if(screen==null){call.reject("Missing screen");return;}
            dialog=new Dialog(getActivity(),android.R.style.Theme_Material_Light_NoActionBar);
            Window win=dialog.getWindow();
            if(win!=null){win.addFlags(WindowManager.LayoutParams.FLAG_SECURE);win.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);}
            dialog.setCancelable(false);
            draw(screen);dialog.show();if(dialog.getWindow()!=null)dialog.getWindow().setLayout(-1,-1);call.resolve();
        });
    }
    @PluginMethod public void render(PluginCall call) {
        getActivity().runOnUiThread(()->{JSObject s=call.getObject("screen");if(dialog==null||s==null){call.reject("Native screen unavailable");return;}draw(s);call.resolve();});
    }
    @PluginMethod public void dismiss(PluginCall call) {
        getActivity().runOnUiThread(()->{edits.clear();selects.clear();optionValues.clear();if(dialog!=null){dialog.dismiss();dialog=null;}call.resolve();});
    }
}

package NATIVE_STAFF_PACKAGE;

import android.app.Dialog;
import android.content.Context;
import android.content.Intent;
import android.app.Activity;
import android.database.Cursor;
import android.provider.OpenableColumns;
import androidx.activity.result.ActivityResult;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import com.getcapacitor.PermissionState;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import android.graphics.Color;
import android.graphics.Bitmap;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import android.util.Base64;
import java.io.File;
import java.io.FileOutputStream;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
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

// Keep complete words together in all native cards, labels and calendar
// controls. Scale the oversized token before Android attempts to wrap it.
final class StaffWordSafeTextView extends TextView {
    private float basePx=0;
    private int baseMaxLines=Integer.MAX_VALUE;
    StaffWordSafeTextView(Context context){super(context);setBreakStrategy(android.text.Layout.BREAK_STRATEGY_SIMPLE);setHyphenationFrequency(android.text.Layout.HYPHENATION_FREQUENCY_NONE);}
    @Override protected void onMeasure(int widthSpec,int heightSpec){
        if(basePx==0){basePx=getTextSize();baseMaxLines=getMaxLines();}
        int mode=MeasureSpec.getMode(widthSpec), width=MeasureSpec.getSize(widthSpec)-getCompoundPaddingLeft()-getCompoundPaddingRight();
        float target=basePx;boolean truncate=false;
        if(mode!=MeasureSpec.UNSPECIFIED&&width>0){android.graphics.Paint paint=new android.graphics.Paint(getPaint());paint.setTextSize(basePx);float longest=0;for(String word:getText().toString().split("\\s+"))longest=Math.max(longest,paint.measureText(word));if(longest>width){target=basePx*width/longest;float min=8*getResources().getDisplayMetrics().scaledDensity;if(target<min){target=min;truncate=true;}}}
        if(Math.abs(getTextSize()-target)>.15f)super.setTextSize(android.util.TypedValue.COMPLEX_UNIT_PX,target);
        int maxLines=truncate?1:baseMaxLines;if(getMaxLines()!=maxLines)setMaxLines(maxLines);
        if(truncate)setEllipsize(android.text.TextUtils.TruncateAt.END);
        super.onMeasure(widthSpec,heightSpec);
    }
}

@CapacitorPlugin(name = "NativeStaff",permissions={@Permission(alias="camera",strings={android.Manifest.permission.CAMERA})})
public final class NativeStaffPlugin extends Plugin {
    private static final int PAPER = Color.rgb(247,245,240);
    private static final int CARD = Color.rgb(255,252,248);
    private static final int INK = Color.rgb(23,41,35);
    private static final int GREEN = Color.rgb(19,37,31);
    private static final int MUTED = Color.rgb(104,115,108);
    private static final int GOLD = Color.rgb(204,171,112);
    private static final int EDGE = Color.rgb(230,223,211);
    private static final int BRONZE = Color.rgb(151,111,58);
    private static final int SAND = Color.rgb(241,229,204);
    private static final int NAVY = Color.rgb(32,43,61);
    private static final int SB_SECTION = Color.rgb(240,243,252), SB_LINE = Color.rgb(220,226,234);
    private TextView sbBookingSave;
    private boolean sbEnglish;
    private static final int WINE = Color.rgb(98,12,14);
    private int accent=GREEN;
    private JSONObject calendarScreen;
    private File cameraFile;
    private Dialog dialog;
    // Keeps direction across the asynchronous native -> Book -> native render.
    private NativeStaffV3Calendar liveCalendar;
    private final Map<String, EditText> edits = new LinkedHashMap<>();
    private final Map<String, String> choices = new LinkedHashMap<>();

    private int dp(float n) { return (int)(n * getContext().getResources().getDisplayMetrics().density + .5f); }
    private GradientDrawable background(int color, int radius) {
        GradientDrawable bg = new GradientDrawable(); bg.setColor(color); bg.setCornerRadius(dp(radius)); return bg;
    }
    private GradientDrawable outlined(int fill, int radius, int border) {
        GradientDrawable bg=background(fill,radius); bg.setStroke(dp(1),border); return bg;
    }
    private LinearLayout column() {
        LinearLayout v = new LinearLayout(getContext()); v.setOrientation(LinearLayout.VERTICAL); return v;
    }
    private LinearLayout row() {
        LinearLayout v = new LinearLayout(getContext()); v.setOrientation(LinearLayout.HORIZONTAL); v.setGravity(Gravity.CENTER_VERTICAL); return v;
    }
    private TextView text(String s, int sp, int color, boolean bold) {
        TextView v = new StaffWordSafeTextView(getContext()); v.setText(s); v.setTextSize(sp); v.setTextColor(color);
        if (bold) v.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return v;
    }
    private Button button(String label, String id, boolean primary) {
        Button v = new Button(getContext()); v.setText(label); v.setAllCaps(false);
        v.setHyphenationFrequency(android.text.Layout.HYPHENATION_FREQUENCY_NONE);v.setSingleLine(true);v.setEllipsize(android.text.TextUtils.TruncateAt.END);if(android.os.Build.VERSION.SDK_INT>=26)v.setAutoSizeTextTypeUniformWithConfiguration(9,14,1,android.util.TypedValue.COMPLEX_UNIT_SP);
        boolean danger=id.contains("cancel-appointment")||id.contains("confirm-cancel")||id.contains("delete-line")||id.contains("remove-block");
        int tone=danger?Color.rgb(158,45,45):accent;
        v.setTextColor(primary&&!danger ? Color.WHITE : tone); v.setMinHeight(dp(49)); v.setMinimumHeight(dp(49));
        v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);v.setTextSize(14);v.setPadding(dp(12),dp(9),dp(12),dp(9));
        v.setMinWidth(0);v.setMinimumWidth(0);v.setStateListAnimator(null);v.setElevation(0);
        v.setBackground(primary&&!danger?background(tone,13):outlined(accent==NAVY?Color.WHITE:Color.rgb(249,243,231),13,EDGE)); v.setOnClickListener(x -> action(id)); return v;
    }
    private void action(String id) {
        if (id.isEmpty()) return;
        JSObject values = new JSObject();
        for (Map.Entry<String,EditText> entry : edits.entrySet()) values.put(entry.getKey(), entry.getValue().getText().toString());
        for (Map.Entry<String,String> entry : choices.entrySet()) values.put(entry.getKey(),entry.getValue());
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
    private void spacer(LinearLayout layout) {
        layout.addView(new View(getContext()),new LinearLayout.LayoutParams(0,dp(1),1));
    }
    private void contentView(View content) {
        // Android 15+ draws dialogs edge-to-edge even when the Activity
        // already handles its own insets. Give all native screens a private
        // safe rectangle; do not place controls beneath system bars/IME.
        FrameLayout safe=new FrameLayout(getContext());safe.setBackgroundColor(PAPER);
        safe.addView(content,new FrameLayout.LayoutParams(-1,-1));
        safe.setOnApplyWindowInsetsListener((view,insets)->{
            if(android.os.Build.VERSION.SDK_INT>=30){
                android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
                android.graphics.Insets ime=insets.getInsets(WindowInsets.Type.ime());
                view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));
                return WindowInsets.CONSUMED;
            }
            view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        dialog.setContentView(safe);
        Window window=dialog.getWindow();
        if(window!=null){
            window.setStatusBarColor(PAPER);window.setNavigationBarColor(PAPER);
            if(android.os.Build.VERSION.SDK_INT>=30){
                window.setDecorFitsSystemWindows(false);
                WindowInsetsController controller=window.getInsetsController();
                if(controller!=null)controller.setSystemBarsAppearance(WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
                    WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
            }else window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        }
        safe.requestApplyInsets();
    }
    private JSONArray list(JSONObject s, String key) {
        JSONArray a = s.optJSONArray(key); return a == null ? new JSONArray() : a;
    }
    private String icon(String id) {
        if(id.startsWith("appointment:")||id.contains("calendar")||id.contains("appointment"))return "◷";
        if(id.startsWith("patient:")||id.contains("patient"))return "♙";
        if(id.contains("billing")||id.contains("invoice")||id.contains("record")||id.contains("intake"))return "▤";
        if(id.equals("settings"))return "⚙";
        return "↗";
    }
    private LinearLayout panel() {
        LinearLayout box=column();box.setPadding(dp(16),dp(14),dp(16),dp(14));box.setBackground(outlined(accent==NAVY?Color.WHITE:CARD,17,EDGE));if(accent!=NAVY)box.setElevation(dp(2));return box;
    }
    private void label(LinearLayout parent,String title) {
        if(title.isEmpty())return;
        TextView t=text(title,11,accent==NAVY?MUTED:BRONZE,true); t.setLetterSpacing(.09f);add(parent,t,9);
    }
    private void grid(LinearLayout parent,JSONArray items,boolean metrics) {
        int available=getContext().getResources().getConfiguration().screenWidthDp;int count=available>=700?3:available<360?1:2;
        for(int i=0;i<items.length();i+=count){
            LinearLayout line=row();line.setGravity(Gravity.TOP);
            for(int k=0;k<count;k++){
                JSONObject item=items.optJSONObject(i+k);
                if(item==null){spacer(line);continue;}
                String id=item.optString("id");
                if(metrics){
                    LinearLayout box=panel();LinearLayout top=row();TextView badge=text(icon(id),21,BRONZE,true);badge.setGravity(Gravity.CENTER);badge.setBackground(background(SAND,10));top.addView(badge,new LinearLayout.LayoutParams(dp(35),dp(35)));spacer(top);top.addView(text("›",19,BRONZE,false));add(box,top,8);
                    TextView caption=text(item.optString("label").toUpperCase(java.util.Locale.GERMANY),10,BRONZE,true);caption.setLetterSpacing(.035f);add(box,caption,4);
                    TextView number=text(item.optString("detail"),31,INK,true);number.setTypeface(Typeface.SERIF,Typeface.BOLD);add(box,number,0);
                    if(!id.isEmpty()){box.setOnClickListener(v->action(id));box.setFocusable(true);}
                    weight(line,box);
                }else {
                    LinearLayout shortcut=row();shortcut.setPadding(dp(10),dp(11),dp(10),dp(11));shortcut.setBackground(outlined(Color.rgb(249,243,231),13,EDGE));
                    TextView glyph=text(icon(id),17,BRONZE,true);glyph.setGravity(Gravity.CENTER);glyph.setBackground(background(SAND,9));shortcut.addView(glyph,new LinearLayout.LayoutParams(dp(31),dp(31)));
                    TextView title=text(item.optString("label"),13,INK,true);title.setPadding(dp(8),0,dp(4),0);shortcut.addView(title,new LinearLayout.LayoutParams(0,-2,1));shortcut.addView(text("›",18,BRONZE,false));shortcut.setOnClickListener(v->action(id));shortcut.setFocusable(true);weight(line,shortcut);
                }
            }add(parent,line,9);
        }
    }
    private void choiceDialog(String key,String title,JSONArray options,TextView control) {
        Dialog choice=new Dialog(getActivity(),android.R.style.Theme_Material_Light_NoActionBar);
        if(choice.getWindow()!=null){
            choice.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
            choice.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
        }
        LinearLayout wrap=column();wrap.setPadding(dp(18),dp(18),dp(18),dp(20));wrap.setBackground(background(PAPER,24));
        LinearLayout header=row();TextView h=text(title,21,INK,true);header.addView(h,new LinearLayout.LayoutParams(0,-2,1));
        Button close=button("×","",false);close.setOnClickListener(v->choice.dismiss());header.addView(close);add(wrap,header,10);
        ScrollView scroll=new ScrollView(getContext());LinearLayout values=column();scroll.addView(values);
        for(int i=0;i<options.length();i++){
            JSONObject item=options.optJSONObject(i);if(item==null)continue;
            String value=item.optString("value"), name=item.optString("label");
            TextView entry=text(name+(value.equals(choices.get(key))?"   ✓":""),15,INK,false);
            entry.setPadding(dp(14),dp(14),dp(14),dp(14));entry.setBackground(outlined(CARD,11,EDGE));
            entry.setOnClickListener(v->{choices.put(key,value);control.setText(name+"   ▾");choice.dismiss();});
            entry.setFocusable(true);add(values,entry,7);
        }
        int maxHeight=Math.min(dp(500),getContext().getResources().getDisplayMetrics().heightPixels/2);
        wrap.addView(scroll,new LinearLayout.LayoutParams(-1,maxHeight));
        choice.setContentView(wrap);choice.show();
        if(choice.getWindow()!=null){choice.getWindow().setLayout(-1,-2);choice.getWindow().setGravity(Gravity.BOTTOM);}
    }
    private void sbDivider(LinearLayout parent){View line=new View(getContext());line.setBackgroundColor(SB_LINE);parent.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));}
    private String sbGlyph(String key){
        if(key.equals("service_id"))return "✦";if(key.equals("staff_id")||key.equals("customer_id"))return "♙";
        if(key.equals("date")||key.equals("operation"))return "▦";if(key.startsWith("start")||key.startsWith("end"))return "◷";
        return "▤";
    }
    private void refreshSbSave(){if(sbBookingSave!=null){boolean ready=!choices.getOrDefault("service_id","").isEmpty()&&!choices.getOrDefault("staff_id","").isEmpty()&&!choices.getOrDefault("customer_id","").isEmpty();sbBookingSave.setEnabled(ready);sbBookingSave.setAlpha(ready?1f:.45f);}}
    private void sbChoice(String key,String title,JSONArray options,TextView control,String initialQuery){
        Dialog chooser=new Dialog(getActivity(),android.R.style.Theme_Material_Light_NoActionBar);
        boolean client=key.equals("customer_id");if(chooser.getWindow()!=null){chooser.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);chooser.getWindow().setBackgroundDrawableResource(android.R.color.transparent);}
        LinearLayout root=column();root.setBackground(background(Color.WHITE,12));root.setPadding(dp(17),dp(17),dp(17),dp(14));root.setFocusableInTouchMode(true);
        TextView heading=text(client?(sbEnglish?"Choose patient":"Patient auswählen"):title,17,NAVY,true);add(root,heading,14);
        LinearLayout search=row();search.setBackground(background(SB_SECTION,5));EditText query=new EditText(getContext());query.setSingleLine(true);query.setText(initialQuery);query.setHint(sbEnglish?"Search...":"Suchen...");query.setTextSize(15);query.setBackgroundColor(Color.TRANSPARENT);query.setPadding(dp(10),0,dp(5),0);query.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH);search.addView(query,new LinearLayout.LayoutParams(0,dp(44),1));TextView find=text("⌕",23,NAVY,true);find.setGravity(Gravity.CENTER);search.addView(find,new LinearLayout.LayoutParams(dp(42),dp(44)));add(root,search,18);
        if(client){TextView addClient=text(sbEnglish?"Add new patient · Web":"Neuen Patienten hinzufügen · Web",14,Color.rgb(0,153,200),true);addClient.setGravity(Gravity.CENTER);addClient.setPadding(0,dp(17),0,dp(14));add(root,addClient,0);}
        ScrollView scroll=new ScrollView(getContext());LinearLayout values=column();scroll.addView(values);
        Runnable populate=()->{values.removeAllViews();for(int i=0;i<options.length();i++){JSONObject option=options.optJSONObject(i);if(option==null)continue;String value=option.optString("value"),name=option.optString("label");if(!client&&!name.toLowerCase(java.util.Locale.ROOT).contains(query.getText().toString().toLowerCase(java.util.Locale.ROOT)))continue;LinearLayout entry=row();entry.setMinimumHeight(dp(49));if(client){TextView initials=text(name.isEmpty()?"?":name.substring(0,1).toUpperCase(java.util.Locale.ROOT),15,Color.WHITE,true);initials.setGravity(Gravity.CENTER);initials.setBackground(background(NAVY,22));entry.addView(initials,new LinearLayout.LayoutParams(dp(35),dp(35)));}LinearLayout copy=column();copy.setPadding(dp(10),dp(5),0,dp(5));add(copy,text(name+(value.equals(choices.get(key))?"  ✓":""),15,NAVY,false),2);if(!option.optString("detail").isEmpty())add(copy,text(option.optString("detail"),11,MUTED,false),0);entry.addView(copy,new LinearLayout.LayoutParams(0,-2,1));values.addView(entry,new LinearLayout.LayoutParams(-1,-2));entry.setOnClickListener(v->{choices.put(key,value);control.setText(name);control.setTypeface(Typeface.DEFAULT,Typeface.BOLD);refreshSbSave();chooser.dismiss();});entry.setFocusable(true);}};
        populate.run();Runnable remote=()->{if(client){choices.put("_patient_query",query.getText().toString());chooser.dismiss();action("calendar-client-search");}else populate.run();};find.setOnClickListener(v->remote.run());query.setOnEditorActionListener((v,id,event)->{remote.run();return true;});query.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){if(!client)populate.run();}public void afterTextChanged(android.text.Editable e){}});
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));TextView cancel=text(sbEnglish?"Cancel":"Abbrechen",15,NAVY,true);cancel.setGravity(Gravity.RIGHT|Gravity.CENTER_VERTICAL);cancel.setMinHeight(dp(45));cancel.setOnClickListener(v->chooser.dismiss());add(root,cancel,0);chooser.setContentView(root);chooser.show();if(chooser.getWindow()!=null){chooser.getWindow().setLayout(Math.min(dp(390),getContext().getResources().getDisplayMetrics().widthPixels-dp(44)),Math.min(dp(640),getContext().getResources().getDisplayMetrics().heightPixels-dp(100)));chooser.getWindow().setGravity(Gravity.CENTER);chooser.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);}
    }
    private JSONObject sbFind(JSONArray fields,String key){for(int i=0;i<fields.length();i++){JSONObject f=fields.optJSONObject(i);if(f!=null&&key.equals(f.optString("id")))return f;}return new JSONObject();}
    private void sbSection(LinearLayout body,String title){TextView label=text(title,17,NAVY,false);label.setGravity(Gravity.CENTER_VERTICAL);label.setPadding(dp(19),0,dp(19),0);label.setBackgroundColor(SB_SECTION);body.addView(label,new LinearLayout.LayoutParams(-1,dp(54)));}
    private EditText sbInput(String key,String value,String hint){EditText input=new EditText(getContext());input.setText(value);input.setHint(hint);input.setTextColor(NAVY);input.setTextSize(16);input.setTypeface(Typeface.DEFAULT,Typeface.BOLD);input.setPadding(0,0,0,0);input.setBackgroundColor(Color.TRANSPARENT);input.setSingleLine();input.setContentDescription(hint);edits.put(key,input);return input;}
    private void sbDatePair(LinearLayout body,JSONArray fields,String time,String label,boolean repeatDate){LinearLayout entry=row();entry.setPadding(dp(19),dp(12),dp(19),dp(12));TextView glyph=text("▦",21,NAVY,false);entry.addView(glyph,new LinearLayout.LayoutParams(dp(28),dp(32)));LinearLayout copy=column();copy.setPadding(dp(14),0,0,0);LinearLayout pair=row();if(repeatDate){TextView date=text(edits.get("date").getText().toString(),16,NAVY,true);pair.addView(date,new LinearLayout.LayoutParams(0,-2,1));edits.get("date").addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){date.setText(s);}public void afterTextChanged(android.text.Editable e){}});}else pair.addView(sbInput("date",sbFind(fields,"date").optString("value"),"TT.MM.JJJJ"),new LinearLayout.LayoutParams(0,-2,1));pair.addView(text(", ",16,NAVY,true));pair.addView(sbInput(time,sbFind(fields,time).optString("value"),"HH:MM"),new LinearLayout.LayoutParams(dp(82),-2));add(copy,pair,4);add(copy,text(label,13,MUTED,false),0);entry.addView(copy,new LinearLayout.LayoutParams(0,-2,1));entry.addView(text("✎",19,NAVY,false));entry.setMinimumHeight(dp(68));add(body,entry,0);sbDivider(body);}
    private void drawSimplyForm(JSONObject s){
        boolean english="en".equals(s.optString("language")),sheet="calendar-sheet".equals(s.optString("presentation"));accent=NAVY;
        sbEnglish=english;sbBookingSave=null;String type=s.optString("formType");boolean booking=type.equals("booking"),block=type.equals("block");
        LinearLayout root=column();root.setBackgroundColor(Color.WHITE);root.setFocusableInTouchMode(true);root.requestFocus();
        JSONArray actions=list(s,"actions");JSONObject primary=null;for(int i=0;i<actions.length();i++){JSONObject a=actions.optJSONObject(i);if(a!=null&&a.optString("id").startsWith("save-")){primary=a;break;}}
        String primaryId=primary==null?"":primary.optString("id");
        LinearLayout header=row();header.setBackgroundColor(NAVY);TextView close=text("×",25,Color.WHITE,false);close.setGravity(Gravity.CENTER);close.setContentDescription(english?"Close":"Schließen");close.setOnClickListener(v->action(sheet?"calendar":"back"));header.addView(close,new LinearLayout.LayoutParams(dp(48),dp(56)));
        TextView heading=text(s.optString("title"),19,Color.WHITE,false);heading.setGravity(Gravity.CENTER_VERTICAL);header.addView(heading,new LinearLayout.LayoutParams(0,dp(56),1));
        if(primary!=null&&!booking){TextView save=text(primary.optString("label"),15,Color.WHITE,true);save.setGravity(Gravity.CENTER);save.setPadding(dp(14),0,dp(14),0);save.setOnClickListener(v->action(primaryId));header.addView(save,new LinearLayout.LayoutParams(-2,dp(56)));}add(root,header,0);
        ScrollView scroll=new ScrollView(getContext());LinearLayout body=column();scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        String section=booking?(english?"Booking info":"Buchungsinformationen"):type.equals("availability")?(english?"Working hours":"Arbeitszeiten"):"Details";sbSection(body,section);
        if(!s.optString("message").isEmpty()){TextView msg=text(s.optString("message"),14,NAVY,false);msg.setPadding(dp(19),dp(12),dp(19),dp(12));msg.setBackgroundColor(SB_SECTION);add(body,msg,0);}
        JSONArray fields=list(s,"fields");Runnable[] reopen={null};
        if(block){sbDatePair(body,fields,"start",english?"Start date and time":"Startdatum und Uhrzeit",false);sbDatePair(body,fields,"end",english?"End date and time":"Enddatum und Uhrzeit",true);
            LinearLayout lock=row();lock.setPadding(dp(19),dp(11),dp(19),dp(11));lock.addView(text("♙",21,NAVY,false),new LinearLayout.LayoutParams(dp(28),dp(36)));LinearLayout copy=column();copy.setPadding(dp(14),0,0,0);boolean blocked="block".equals(sbFind(fields,"kind").optString("value"));choices.put("kind",blocked?"block":"note");TextView state=text(blocked?(english?"Time is blocked":"Zeitraum ist geblockt"):(english?"Time is not blocked":"Zeitraum ist nicht geblockt"),16,NAVY,true);add(copy,state,4);add(copy,text(english?"Time is blocked":"Zeitraum ist geblockt",13,MUTED,false),0);lock.addView(copy,new LinearLayout.LayoutParams(0,-2,1));Switch toggle=new Switch(getContext());toggle.setChecked(blocked);toggle.setContentDescription(english?"Time is blocked":"Zeitraum ist geblockt");toggle.setOnCheckedChangeListener((b,on)->{choices.put("kind",on?"block":"note");state.setText(on?(english?"Time is blocked":"Zeitraum ist geblockt"):(english?"Time is not blocked":"Zeitraum ist nicht geblockt"));});lock.addView(toggle);add(body,lock,0);sbSection(body,english?"Apply note to":"Anwendung der Notiz");
            LinearLayout scope=row();String[] scopes=english?new String[]{"Apply to all","Apply to provider","Apply to service"}:new String[]{"Für alle anwenden","Für Dienstleister anwenden","Für Dienstleistung anwenden"};for(int n=0;n<3;n++){TextView tab=text(scopes[n],12,n==1?NAVY:MUTED,n==1);tab.setGravity(Gravity.CENTER);tab.setPadding(dp(5),0,dp(5),0);tab.setBackgroundColor(n==1?Color.WHITE:SB_SECTION);scope.addView(tab,new LinearLayout.LayoutParams(0,dp(64),1));}add(body,scope,0);
        }
        for(int i=0;i<fields.length();i++){
            JSONObject f=fields.optJSONObject(i);if(f==null)continue;String key=f.optString("id"),label=f.optString("label"),kind=f.optString("kind"),value=f.optString("value");
            if(block&&!(key.equals("staff_id")||key.equals("text")))continue;
            if(booking&&key.equals("start"))continue;
            if(booking&&key.equals("date")){sbDatePair(body,fields,"start",english?"Booking date and time":"Datum und Uhrzeit der Buchung",false);LinearLayout recurring=row();recurring.setPadding(dp(19),dp(12),dp(19),dp(12));recurring.setBackgroundColor(SB_SECTION);TextView labelView=text(english?"Recurring booking settings":"Einstellungen wiederkehrende Buchungen",15,NAVY,false);recurring.addView(labelView,new LinearLayout.LayoutParams(0,-2,1));Switch toggle=new Switch(getContext());toggle.setEnabled(false);toggle.setContentDescription(english?"Recurring bookings · web only":"Wiederkehrende Buchungen · nur Web");recurring.addView(toggle);add(body,recurring,0);continue;}
            LinearLayout entry=row();entry.setPadding(dp(18),dp(11),dp(18),dp(11));entry.setMinimumHeight(dp(65));TextView glyph=text(sbGlyph(key),21,NAVY,false);glyph.setGravity(Gravity.CENTER);entry.addView(glyph,new LinearLayout.LayoutParams(dp(27),dp(36)));
            LinearLayout copy=column();copy.setPadding(dp(14),0,dp(12),0);entry.addView(copy,new LinearLayout.LayoutParams(0,-2,1));JSONArray options=f.optJSONArray("options");
            TextView end=text(options!=null?"⌄":"✎",21,NAVY,false);end.setGravity(Gravity.CENTER);entry.addView(end,new LinearLayout.LayoutParams(dp(23),dp(36)));
            if(options!=null){choices.put(key,value);String selected=key.equals("service_id")?(english?"Choose a service":"Eine Dienstleistung auswählen"):key.equals("customer_id")?(english?"Choose a patient":"Patient auswählen"):(english?"Select":"Auswählen");for(int n=0;n<options.length();n++){JSONObject o=options.optJSONObject(n);if(o!=null&&value.equals(o.optString("value"))){selected=o.optString("label");break;}}
                TextView picker=text(selected,17,NAVY,!value.isEmpty());add(copy,picker,4);entry.setOnClickListener(v->sbChoice(key,label,options,picker,""));entry.setFocusable(true);entry.setContentDescription(label+", "+selected);if(key.equals(s.optString("openChoice")))reopen[0]=()->sbChoice(key,label,options,picker,s.optString("choiceQuery"));
            }else{EditText input=new EditText(getContext());input.setText(value);input.setHint(label);input.setTextColor(NAVY);input.setTextSize(17);input.setTypeface(Typeface.DEFAULT,Typeface.BOLD);input.setPadding(0,0,0,0);input.setBackgroundColor(Color.TRANSPARENT);input.setContentDescription(label);input.setSingleLine(!kind.equals("multiline"));if(kind.equals("multiline"))input.setMinLines(2);add(copy,input,3);edits.put(key,input);end.setOnClickListener(v->{input.requestFocus();((android.view.inputmethod.InputMethodManager)getContext().getSystemService(Context.INPUT_METHOD_SERVICE)).showSoftInput(input,android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT);});}
            add(copy,text(label,13,MUTED,false),0);add(body,entry,0);sbDivider(body);
        }
        if(block){LinearLayout note=row();note.setPadding(dp(19),dp(12),dp(19),dp(12));TextView badge=text("N",16,Color.WHITE,true);badge.setGravity(Gravity.CENTER);badge.setBackground(background(Color.rgb(244,198,92),22));note.addView(badge,new LinearLayout.LayoutParams(dp(35),dp(35)));LinearLayout copy=column();copy.setPadding(dp(14),0,0,0);add(copy,text("Note",16,NAVY,true),3);add(copy,text(english?"Note type":"Art der Notiz",13,MUTED,false),0);note.addView(copy,new LinearLayout.LayoutParams(0,-2,1));add(body,note,0);}
        JSONArray rows=list(s,"rows");for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item==null)continue;TextView r=text(item.optString("label")+"  "+item.optString("detail"),15,NAVY,false);r.setPadding(dp(19),dp(16),dp(19),dp(16));add(body,r,0);sbDivider(body);}
        for(int i=0;i<actions.length();i++){JSONObject item=actions.optJSONObject(i);if(item==null||primaryId.equals(item.optString("id")))continue;String actionId=item.optString("id");TextView link=text(item.optString("label"),15,actionId.contains("remove")?Color.RED:Color.rgb(0,153,200),true);link.setBackgroundColor(SB_SECTION);link.setGravity(Gravity.CENTER);link.setMinHeight(dp(53));link.setOnClickListener(v->action(actionId));add(body,link,0);}
        if(booking&&primary!=null){TextView save=text(primary.optString("label"),16,Color.WHITE,true);save.setGravity(Gravity.CENTER);save.setBackground(background(Color.rgb(0,153,200),28));save.setOnClickListener(v->action(primaryId));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(49));p.setMargins(dp(20),dp(12),dp(20),dp(12));root.addView(save,p);if(primaryId.equals("save-new")){sbBookingSave=save;refreshSbSave();}}
        contentView(root);if(reopen[0]!=null)root.post(reopen[0]);
    }
    private void draw(JSONObject s) {
        edits.clear(); choices.clear();
        if(s.optJSONObject("timeline") != null) {
            calendarScreen=s;
            if(liveCalendar!=null){liveCalendar.update(s);return;}
            liveCalendar=new NativeStaffV3Calendar(getActivity(),s,this::action);
            contentView(liveCalendar.build());
            return;
        }
        liveCalendar=null;
        if("simplybook-form".equals(s.optString("layout"))){drawSimplyForm(s);return;}
        boolean sheet="calendar-sheet".equals(s.optString("presentation"));
        boolean english="en".equals(s.optString("language"));
        accent=sheet?NAVY:"billing".equals(s.optString("theme"))?WINE:GREEN;
        LinearLayout root = column(); root.setBackground(background(PAPER,sheet?24:0));
        root.setPadding(dp(14),dp(12),dp(14),dp(8));
        LinearLayout header = row();
        Button back=button(sheet?"×":"‹",sheet?"calendar":"back",false);header.addView(back,new LinearLayout.LayoutParams(dp(46),dp(46)));
        TextView brand = text(sheet?(english?"CALENDAR":"KALENDER"):"A+ ESTHETIC",12,accent,true); brand.setLetterSpacing(.12f);brand.setGravity(Gravity.CENTER);
        header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
        if(sheet)header.addView(new View(getContext()),new LinearLayout.LayoutParams(dp(46),dp(1)));
        else header.addView(button("⌂","home",false),new LinearLayout.LayoutParams(dp(46),dp(46)));add(root,header,12);
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
        ScrollView scroll = new ScrollView(getContext()) {
            private float downX, downY;
            private boolean swiping;
            @Override public boolean onInterceptTouchEvent(android.view.MotionEvent e) {
                if(week.length()==0)return super.onInterceptTouchEvent(e);
                if(e.getActionMasked()==android.view.MotionEvent.ACTION_DOWN){
                    downX=e.getX(); downY=e.getY(); swiping=false;
                }
                if(e.getActionMasked()==android.view.MotionEvent.ACTION_MOVE){
                    float dx=e.getX()-downX, dy=e.getY()-downY;
                    if(Math.abs(dx)>dp(28)&&Math.abs(dx)>Math.abs(dy)*1.4f){
                        swiping=true; return true;
                    }
                }
                return super.onInterceptTouchEvent(e);
            }
            @Override public boolean onTouchEvent(android.view.MotionEvent e) {
                if(swiping){
                    if(e.getActionMasked()==android.view.MotionEvent.ACTION_UP){
                        float dx=e.getX()-downX, dy=e.getY()-downY;
                        if(Math.abs(dx)>dp(60)&&Math.abs(dx)>Math.abs(dy)*1.4f)
                            action(dx<0?"day-next":"day-prev");
                        swiping=false;
                    }else if(e.getActionMasked()==android.view.MotionEvent.ACTION_CANCEL){
                        swiping=false;
                    }
                    return true;
                }
                return super.onTouchEvent(e);
            }
        };
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout body=column(); body.setPadding(0,0,0,dp(12)); scroll.addView(body);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        if(!s.optString("hero").isEmpty()){
            LinearLayout hero=column();hero.setPadding(dp(22),dp(23),dp(22),dp(23));
            GradientDrawable gradient=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{GREEN,Color.rgb(48,74,61)});
            gradient.setCornerRadius(dp(23));hero.setBackground(gradient);
            hero.setElevation(dp(5));TextView overline=text("A+ ESTHETIC · "+s.optString("heroLabel",english?"PRACTICE MANAGEMENT":"PRAXISMANAGEMENT"),10,GOLD,true);overline.setLetterSpacing(.1f);
            add(hero,overline,12);TextView title=text(s.optString("hero"),33,Color.WHITE,false);title.setTypeface(Typeface.SERIF);add(hero,title,10);
            add(hero,text(s.optString("subtitle"),14,Color.rgb(235,233,222),false),0);add(body,hero,12);
        }else{
            TextView title=text(s.optString("title"),sheet?27:32,INK,false);title.setTypeface(sheet?Typeface.DEFAULT:Typeface.SERIF);
            add(body,title,5);if(!s.optString("subtitle").isEmpty())add(body,text(s.optString("subtitle"),14,MUTED,false),12);
        }
        if(s.optBoolean("busy")) { for(int i=0;i<3;i++){View skeleton=new View(getContext());skeleton.setBackground(background(EDGE,13));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(70));p.bottomMargin=dp(10);body.addView(skeleton,p);} }
        grid(body,list(s,"metrics"),true);
        JSONArray segments=list(s,"segments");
        if(segments.length()>0){
            HorizontalScrollView chips=new HorizontalScrollView(getContext());chips.setHorizontalScrollBarEnabled(false);LinearLayout strip=row();
            for(int i=0;i<segments.length();i++){JSONObject item=segments.optJSONObject(i);if(item!=null){Button chip=button(item.optString("label"),item.optString("id"),item.optBoolean("selected"));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2);p.rightMargin=dp(6);strip.addView(chip,p);}}
            chips.addView(strip);add(body,chips,10);
        }
        if(!s.optString("message").isEmpty()) {
            TextView msg=text(s.optString("message"),15,INK,false); msg.setPadding(dp(14),dp(14),dp(14),dp(14));
            msg.setBackground(outlined(CARD,14,EDGE));add(body,msg,10);
        }
        JSONArray fields=list(s,"fields");
        for(int i=0;i<fields.length();i++){
            JSONObject f=fields.optJSONObject(i);if(f==null)continue;
            String key=f.optString("id"); LinearLayout container=panel();
            add(container,text(f.optString("label"),13,MUTED,true),7);
            JSONArray options=f.optJSONArray("options");
            if(options!=null&&options.length()>0){
                String selected=f.optString("value"), selectedLabel=english?"Select":"Auswählen";
                for(int j=0;j<options.length();j++){JSONObject option=options.optJSONObject(j);if(option!=null&&option.optString("value").equals(selected))selectedLabel=option.optString("label");}
                choices.put(key,selected);
                if("choice-grid".equals(f.optString("kind"))){
                    Map<String,Button> tiles=new LinkedHashMap<>();
                    for(int j=0;j<options.length();j+=2){
                        LinearLayout pair=row();
                        for(int k=0;k<2;k++){
                            JSONObject item=options.optJSONObject(j+k);
                            if(item==null){spacer(pair);continue;}
                            String keyValue=item.optString("value");
                            Button tile=button(item.optString("label"),"",keyValue.equals(selected));
                            tiles.put(keyValue,tile);
                            tile.setOnClickListener(v->{choices.put(key,keyValue);for(Map.Entry<String,Button> tileEntry:tiles.entrySet()){
                                boolean marked=tileEntry.getKey().equals(keyValue);
                                tileEntry.getValue().setTextColor(marked?Color.WHITE:accent);
                                tileEntry.getValue().setBackground(marked?background(accent,10):outlined(CARD,10,EDGE));
                            }});
                            weight(pair,tile);
                        }
                        add(container,pair,7);
                    }
                }else{
                    TextView picker=text(selectedLabel+"   ▾",16,INK,false);picker.setMinHeight(dp(48));picker.setGravity(Gravity.CENTER_VERTICAL);
                    picker.setPadding(dp(12),dp(9),dp(12),dp(9));picker.setBackground(outlined(PAPER,11,EDGE));picker.setFocusable(true);
                    picker.setOnClickListener(v->choiceDialog(key,f.optString("label"),options,picker));add(container,picker,0);
                }
            } else {
                EditText input=new EditText(getContext());
                String kind=f.optString("kind","text");
                int inputType;
                switch(kind){
                    case "multiline":
                        inputType=android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE
                            | android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES;
                        break;
                    case "integer":
                        inputType=android.text.InputType.TYPE_CLASS_NUMBER;
                        break;
                    case "decimal":
                        inputType=android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL;
                        break;
                    case "email":
                        inputType=android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS;
                        break;
                    case "phone":
                        inputType=android.text.InputType.TYPE_CLASS_PHONE;
                        break;
                    default:
                        inputType=android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES;
                }
                input.setInputType(inputType);
                if("multiline".equals(kind)){
                    input.setSingleLine(false);
                    input.setMinLines(3);
                    input.setMaxLines(7);
                    input.setGravity(Gravity.TOP | Gravity.START);
                } else {
                    input.setSingleLine(true);
                    input.setMinHeight(dp(48));
                }
                input.setText(f.optString("value"));input.setTextColor(INK);input.setTextSize(16);
                input.setHint(f.optString("label"));input.setPadding(dp(12),dp(10),dp(12),dp(10));input.setBackground(outlined(PAPER,11,EDGE));add(container,input,0);edits.put(key,input);
            }
            add(body,container,10);
        }
        JSONArray shortcuts=list(s,"shortcuts");if(shortcuts.length()>0){label(body,english?"QUICK ACCESS":"SCHNELLZUGRIFF");grid(body,shortcuts,false);}
        label(body,s.optString("sectionTitle"));JSONArray rows=list(s,"rows");
        for(int i=0;i<rows.length();i++){
            JSONObject item=rows.optJSONObject(i);if(item==null)continue;
            LinearLayout box=panel();LinearLayout content=row();String id=item.optString("id");
            if(!id.isEmpty()){
                TextView symbol=text(icon(id),22,accent==NAVY?NAVY:BRONZE,true);symbol.setGravity(Gravity.CENTER);symbol.setBackground(background(accent==NAVY?PAPER:SAND,12));
                LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(43),dp(43));p.rightMargin=dp(12);content.addView(symbol,p);
            }
            LinearLayout copy=column();add(copy,text(item.optString("label"),16,INK,true),5);if(!item.optString("detail").isEmpty())add(copy,text(item.optString("detail"),13,MUTED,false),0);
            if(!item.optString("badge").isEmpty()){TextView status=text(item.optString("badge"),12,accent==NAVY?NAVY:BRONZE,true);status.setPadding(dp(8),dp(4),dp(8),dp(4));status.setBackground(background(accent==NAVY?PAPER:SAND,8));copy.addView(status,new LinearLayout.LayoutParams(-2,-2));}
            content.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
            if(!id.isEmpty()){TextView more=text("›",21,MUTED,false);content.addView(more);box.setOnClickListener(x->action(id));box.setFocusable(true);}
            add(box,content,0);
            add(body,box,10);
        }
        if(rows.length()==0&&!s.optString("empty").isEmpty()){LinearLayout empty=panel();TextView message=text(s.optString("empty"),14,MUTED,false);message.setGravity(Gravity.CENTER);add(empty,message,0);add(body,empty,10);}
        JSONArray secondary=list(s,"secondaryRows");if(secondary.length()>0){
            label(body,s.optString("secondaryTitle"));
            for(int i=0;i<secondary.length();i++){
                JSONObject item=secondary.optJSONObject(i);if(item==null)continue;
                LinearLayout box=panel();add(box,text(item.optString("label"),16,INK,true),5);add(box,text(item.optString("detail"),13,MUTED,false),0);
                String id=item.optString("id");if(!id.isEmpty()){box.setOnClickListener(v->action(id));box.setFocusable(true);}add(body,box,9);
            }
        }
        String image=s.optString("image");if(!image.isEmpty()&&image.length()<11000000){
            try{byte[] bytes=Base64.decode(image,Base64.DEFAULT);Bitmap bitmap=android.graphics.BitmapFactory.decodeByteArray(bytes,0,bytes.length);
                if(bitmap!=null){ImageView photo=new ImageView(getContext());photo.setImageBitmap(bitmap);photo.setAdjustViewBounds(true);photo.setMaxHeight(dp(480));add(body,photo,10);}
            }catch(IllegalArgumentException ignored){}
        }
        JSONArray actions=list(s,"actions");
        for(int i=0;i<actions.length();i++){JSONObject item=actions.optJSONObject(i);if(item!=null)add(body,button(item.optString("label"),item.optString("id"),i==0),10);}
        JSONArray tabs=list(s,"tabs"); LinearLayout nav=row();
        if(!sheet){
            for(int i=0;i<tabs.length();i++){JSONObject item=tabs.optJSONObject(i);if(item!=null){String id=item.optString("id");boolean selected=item.optBoolean("selected");
                LinearLayout tab=column();tab.setGravity(Gravity.CENTER);tab.setPadding(dp(1),dp(9),dp(1),dp(9));tab.setBackground(background(selected?accent:CARD,13));
                TextView glyph=text(icon(id),20,selected?Color.WHITE:MUTED,true);glyph.setGravity(Gravity.CENTER);add(tab,glyph,3);
                TextView caption=text(item.optString("label"),10,selected?Color.WHITE:MUTED,selected);caption.setGravity(Gravity.CENTER);caption.setMaxLines(1);add(tab,caption,0);
                tab.setOnClickListener(v->action(id));tab.setFocusable(true);weight(nav,tab);
            }}add(root,nav,0);
        }
        if(sheet&&calendarScreen!=null){
            FrameLayout frame=new FrameLayout(getContext());
            View calendar=new NativeStaffV3Calendar(getActivity(),calendarScreen,id->{}).build();frame.addView(calendar,new FrameLayout.LayoutParams(-1,-1));
            View dim=new View(getContext());dim.setBackgroundColor(0x66000000);dim.setOnClickListener(v->action("calendar"));frame.addView(dim,new FrameLayout.LayoutParams(-1,-1));
            FrameLayout.LayoutParams sheetParams=new FrameLayout.LayoutParams(-1,-1,Gravity.BOTTOM);
            sheetParams.topMargin=dp(100);frame.addView(root,sheetParams);contentView(frame);
        }else contentView(root);
    }
    @Override public void load() {
        super.load();
        // ADB-only synthetic visual fixture on a debuggable emulator. This
        // dialog has no authenticated controller or server interaction.
        Activity activity=getActivity();
        if(activity==null||(activity.getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)==0)return;
        if(!android.os.Build.FINGERPRINT.contains("generic")&&!android.os.Build.HARDWARE.contains("ranchu"))return;
        String payload=activity.getIntent().getStringExtra("APLUS_NATIVE_QA_FIXTURE");
        if(payload==null||payload.length()>160000)return;
        activity.getWindow().getDecorView().postDelayed(()->{
            try{
                JSONObject fixture=new JSONObject(new String(Base64.decode(payload,Base64.DEFAULT),java.nio.charset.StandardCharsets.UTF_8));
                JSONObject screen=fixture.getJSONObject("screen");
                calendarScreen=fixture.optJSONObject("calendar");
                dialog=new Dialog(activity,android.R.style.Theme_Material_Light_NoActionBar);
                dialog.setCancelable(false);
                draw(screen);dialog.show();if(dialog.getWindow()!=null)dialog.getWindow().setLayout(-1,-1);
                JSONArray transitions=fixture.optJSONArray("transitions");
                if(transitions!=null&&transitions.length()>0){
                    NativeStaffV3Calendar initial=liveCalendar;
                    View root=dialog.findViewById(android.R.id.content);
                    if(initial==null||root==null)throw new IllegalStateException("Calendar QA missing initial root");
                    final View header=initial.qaHeader();
                    final View body=initial.qaGrid();
                    for(int i=0;i<transitions.length();i++){
                        draw(transitions.getJSONObject(i));
                        if(liveCalendar!=initial||dialog.findViewById(android.R.id.content)!=root||initial.qaHeader()!=header||initial.qaGrid()==body)
                            throw new IllegalStateException("Calendar root/header rebuilt or grid did not update");
                    }
                    android.util.Log.i("APlusCalendarQA","PASS B62 calendar header and native root retained across day/week updates");
                }
            }catch(Exception ignored){if(dialog!=null)dialog.dismiss();dialog=null;liveCalendar=null;}
        },700);
    }
    @PluginMethod public void probe(PluginCall call) {
        JSObject result=new JSObject();result.put("ok",true);result.put("native",true);
        result.put("bridge","NativeStaff");call.resolve(result);
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
    @PluginMethod public void pickPDF(PluginCall call) {
        getActivity().runOnUiThread(()->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.setType("application/pdf");
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            startActivityForResult(call,intent,"pickPDFResult");
        });
    }
    @PluginMethod public void pickPhoto(PluginCall call) {
        getActivity().runOnUiThread(()->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.setType("image/*");intent.addCategory(Intent.CATEGORY_OPENABLE);
            startActivityForResult(call,intent,"pickPhotoResult");
        });
    }
    @PluginMethod public void takePhoto(PluginCall call) {
        if(getPermissionState("camera")!=PermissionState.GRANTED){requestPermissionForAlias("camera",call,"cameraPermissionResult");return;}
        launchCamera(call);
    }
    @PermissionCallback private void cameraPermissionResult(PluginCall call) {
        if(getPermissionState("camera")==PermissionState.GRANTED)launchCamera(call);else call.reject("Camera permission denied");
    }
    private void launchCamera(PluginCall call) {
        getActivity().runOnUiThread(()->{
            if(cameraFile!=null){call.reject("Camera already active");return;}
            try{
                File folder=new File(getContext().getCacheDir(),"staff-photos");
                if(!folder.exists()&&!folder.mkdirs())throw new java.io.IOException("Unable to prepare photo");
                cameraFile=File.createTempFile("staff-",".jpg",folder);
                android.net.Uri uri=androidx.core.content.FileProvider.getUriForFile(getContext(),getContext().getPackageName()+".fileprovider",cameraFile);
                Intent capture=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
                capture.putExtra(android.provider.MediaStore.EXTRA_OUTPUT,uri);
                capture.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivityForResult(call,capture,"cameraResult");
            }catch(Exception e){if(cameraFile!=null)cameraFile.delete();cameraFile=null;call.reject("Camera unavailable");}
        });
    }
    @ActivityCallback private void pickPhotoResult(PluginCall call,ActivityResult result) {
        if(call==null)return;
        if(result.getResultCode()!=Activity.RESULT_OK||result.getData()==null||result.getData().getData()==null){JSObject cancelled=new JSObject();cancelled.put("cancelled",true);call.resolve(cancelled);return;}
        final android.net.Uri uri=result.getData().getData();
        new Thread(()->{
            try(InputStream in=getContext().getContentResolver().openInputStream(uri)){
                if(in==null)throw new java.io.IOException("No photo");
                resolvePhoto(call,in);
            }catch(Exception e){call.reject("Unable to read photo");}
        }).start();
    }
    @ActivityCallback private void cameraResult(PluginCall call,ActivityResult result) {
        File photo=cameraFile;cameraFile=null;
        if(call==null){if(photo!=null)photo.delete();return;}
        if(result.getResultCode()!=Activity.RESULT_OK||photo==null){if(photo!=null)photo.delete();JSObject cancelled=new JSObject();cancelled.put("cancelled",true);call.resolve(cancelled);return;}
        new Thread(()->{
            try(InputStream in=new java.io.FileInputStream(photo)){resolvePhoto(call,in);}
            catch(Exception e){call.reject("Unable to read photo");}finally{photo.delete();}
        }).start();
    }
    private void resolvePhoto(PluginCall call,InputStream in) throws java.io.IOException {
        ByteArrayOutputStream original=new ByteArrayOutputStream();byte[] buffer=new byte[16384];int count;
        while((count=in.read(buffer))!=-1){if(original.size()+count>32*1024*1024)throw new java.io.IOException("Image too large");original.write(buffer,0,count);}
        byte[] raw=original.toByteArray();
        android.graphics.BitmapFactory.Options bounds=new android.graphics.BitmapFactory.Options();bounds.inJustDecodeBounds=true;
        android.graphics.BitmapFactory.decodeByteArray(raw,0,raw.length,bounds);
        if(bounds.outWidth<=0||bounds.outHeight<=0||Math.max(bounds.outWidth,bounds.outHeight)>15000)throw new java.io.IOException("Invalid image");
        android.graphics.BitmapFactory.Options opts=new android.graphics.BitmapFactory.Options();opts.inSampleSize=1;
        while(Math.max(bounds.outWidth,bounds.outHeight)/opts.inSampleSize>3000)opts.inSampleSize*=2;
        Bitmap bitmap=android.graphics.BitmapFactory.decodeByteArray(raw,0,raw.length,opts);
        if(bitmap==null)throw new java.io.IOException("Invalid image");
        try{
            int orientation=new android.media.ExifInterface(new java.io.ByteArrayInputStream(raw)).getAttributeInt(android.media.ExifInterface.TAG_ORIENTATION,1);
            android.graphics.Matrix matrix=new android.graphics.Matrix();
            if(orientation==6)matrix.postRotate(90);else if(orientation==3)matrix.postRotate(180);else if(orientation==8)matrix.postRotate(270);
            if(!matrix.isIdentity()){Bitmap rotated=Bitmap.createBitmap(bitmap,0,0,bitmap.getWidth(),bitmap.getHeight(),matrix,true);if(rotated!=bitmap)bitmap.recycle();bitmap=rotated;}
        }catch(Exception ignored){}
        ByteArrayOutputStream output=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.JPEG,86,output);bitmap.recycle();
        if(output.size()>6*1024*1024)throw new java.io.IOException("Image too large");
        JSObject response=new JSObject();response.put("filename","patient-photo.jpg");response.put("base64",Base64.encodeToString(output.toByteArray(),Base64.NO_WRAP));call.resolve(response);
    }
    @ActivityCallback private void pickPDFResult(PluginCall call, ActivityResult result) {
        if(call==null)return;
        if(result.getResultCode()!=Activity.RESULT_OK||result.getData()==null||result.getData().getData()==null){
            JSObject response=new JSObject();response.put("cancelled",true);call.resolve(response);return;
        }
        final android.net.Uri uri=result.getData().getData();
        new Thread(()->{
            try {
                String filename="document.pdf";
                try(Cursor cursor=getContext().getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                    if(cursor!=null&&cursor.moveToFirst())filename=cursor.getString(0);
                }
                try(InputStream in=getContext().getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){
                    if(in==null)throw new java.io.IOException("No content");
                    byte[] chunk=new byte[16384];int count;
                    while((count=in.read(chunk))!=-1){
                        if(out.size()+count>6*1024*1024){call.reject("File exceeds 6 MB");return;}
                        out.write(chunk,0,count);
                    }
                    byte[] data=out.toByteArray();
                    if(data.length<5||data[0]!='%'||data[1]!='P'||data[2]!='D'||data[3]!='F'||data[4]!='-'){call.reject("Invalid PDF");return;}
                    JSObject response=new JSObject();response.put("filename",filename);response.put("base64",Base64.encodeToString(data,Base64.NO_WRAP));call.resolve(response);
                }
            } catch(Exception e){call.reject("Unable to read PDF");}
        }).start();
    }
    @PluginMethod public void previewPDF(PluginCall call) {
        getActivity().runOnUiThread(()->{
            String base64=call.getString("base64");
            if(dialog==null||base64==null||base64.length()>11000000){call.reject("PDF unavailable");return;}
            File temp=null;
            try {
                temp=File.createTempFile("staff-pdf-", ".pdf", getContext().getCacheDir());
                try(FileOutputStream out=new FileOutputStream(temp)){out.write(Base64.decode(base64, Base64.DEFAULT));}
                final File privateFile=temp;
                final PdfRenderer pdf=new PdfRenderer(ParcelFileDescriptor.open(temp,ParcelFileDescriptor.MODE_READ_ONLY));
                final Dialog preview=new Dialog(getActivity(),android.R.style.Theme_Material_Light_NoActionBar);
                if(preview.getWindow()!=null)preview.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
                LinearLayout root=column();root.setBackgroundColor(PAPER);root.setPadding(dp(12),dp(12),dp(12),dp(12));
                add(root,text(call.getString("title","PDF"),20,GREEN,true),10);
                ScrollView scroll=new ScrollView(getContext()); ImageView image=new ImageView(getContext());image.setAdjustViewBounds(true);
                scroll.addView(image,new ScrollView.LayoutParams(-1,-2));root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
                final int[] index={0};
                final Bitmap[] bitmap={null};
                Runnable drawPage=()->{
                    try(PdfRenderer.Page page=pdf.openPage(index[0])){
                        int width=Math.min(1400, Math.max(600,page.getWidth()*2));
                        int height=Math.max(1,(int)((long)page.getHeight()*width/page.getWidth()));
                        height=Math.min(height,2600);
                        Bitmap next=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);
                        next.eraseColor(Color.WHITE);page.render(next,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                        image.setImageBitmap(next);if(bitmap[0]!=null)bitmap[0].recycle();bitmap[0]=next;
                    }
                };
                LinearLayout buttons=row();
                Button prev=button("‹","",false);prev.setOnClickListener(v->{if(index[0]>0){index[0]--;drawPage.run();}});
                Button next=button("›","",false);next.setOnClickListener(v->{if(index[0]+1<pdf.getPageCount()){index[0]++;drawPage.run();}});
                Button close=button("OK","",true);close.setOnClickListener(v->preview.dismiss());
                weight(buttons,prev);weight(buttons,next);weight(buttons,close);add(root,buttons,0);
                preview.setOnDismissListener(d->{image.setImageDrawable(null);if(bitmap[0]!=null)bitmap[0].recycle();pdf.close();privateFile.delete();});
                preview.setContentView(root);drawPage.run();preview.show();if(preview.getWindow()!=null)preview.getWindow().setLayout(-1,-1);call.resolve();
            } catch(Exception e){if(temp!=null)temp.delete();call.reject("PDF unavailable");}
        });
    }
    @PluginMethod public void dismiss(PluginCall call) {
        getActivity().runOnUiThread(()->{edits.clear();choices.clear();calendarScreen=null;liveCalendar=null;if(dialog!=null){dialog.dismiss();dialog=null;}call.resolve();});
    }
}

package NATIVE_STAFF_PACKAGE;

// A+ Esthetic V3 native calendar for Android. Mirrors the iOS SimplyBook-style
// staff timeline, without a WebView and without copying patient data locally.
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.ColorDrawable;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

final class NativeStaffV3Calendar {
    interface Action {
        void send(String id);
    }
    private static final int NAVY=Color.rgb(32,43,61);
    private static final int PINK=Color.rgb(249,27,82);
    private static final int BLUE=Color.rgb(0,153,200);
    private static final int AMBER=Color.rgb(255,190,103);
    private static final int INK=Color.rgb(42,48,58);
    private static final int MUTED=Color.rgb(128,133,142);
    private static final int LINES=Color.rgb(220,226,234);
    private static final int RULER=Color.rgb(246,247,251);
    private static final int PALE=Color.rgb(255,250,235);
    private final Context ctx;
    private JSONObject screen;
    private JSONObject model;
    private final Action callback;
    private final boolean english;
    private final int hourStart;
    private final int hourEnd;
    private final int hourHeight;
    private final int rulerWidth;
    private View animatedPage;
    private ScrollView verticalScroll;
    private FrameLayout dateHost, timelineHost;
    private TextView headerTitle, monthLabel;
    private NativeStaffV3Calendar gridRenderer;
    private View gridView;
    private int generation;

    NativeStaffV3Calendar(Context context, JSONObject screen, Action callback) {
        this.ctx=context;
        this.screen=screen;
        this.model=screen.optJSONObject("timeline");
        this.callback=callback;
        this.english="en".equals(model.optString("language"));
        this.hourStart=Math.max(0,Math.min(23,model.optInt("firstHour",10)));
        this.hourEnd=Math.max(hourStart+1,Math.min(24,model.optInt("lastHour",20)));
        this.hourHeight=d(82);
        this.rulerWidth=d(56);
    }
    private int d(float dp){return (int)(dp*ctx.getResources().getDisplayMetrics().density+.5f);}
    private String t(String german,String englishText){return english?englishText:german;}
    private JSONArray array(String key){JSONArray a=model.optJSONArray(key);return a==null?new JSONArray():a;}
    private String str(JSONObject row,String key){return row==null?"":row.optString(key,"");}
    private JSONObject at(JSONArray a,int idx){JSONObject o=a.optJSONObject(idx);return o==null?new JSONObject():o;}
    private GradientDrawable shape(int color,int radius) {
        GradientDrawable out=new GradientDrawable();
        out.setColor(color);
        out.setCornerRadius(d(radius));
        return out;
    }
    private GradientDrawable oval(int color) {
        GradientDrawable out=new GradientDrawable();
        out.setColor(color);out.setShape(GradientDrawable.OVAL);return out;
    }
    private LinearLayout vertical(){
        LinearLayout l=new LinearLayout(ctx);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }
    private LinearLayout horizontal(){
        LinearLayout l=new LinearLayout(ctx);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }
    private LinearLayout.LayoutParams lp(int w,int h){return new LinearLayout.LayoutParams(w,h);}
    private TextView text(String text,float sp,int color,boolean bold) {
        TextView out=new StaffWordSafeTextView(ctx);
        out.setText(text);out.setTextSize(sp);out.setTextColor(color);
        if(bold)out.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        out.setGravity(Gravity.CENTER_VERTICAL);
        out.setIncludeFontPadding(false);
        return out;
    }
    private TextView clickable(String label,int color,int background,Runnable action,String description) {
        TextView v=text(label,16,color,false);
        v.setGravity(Gravity.CENTER);
        if(background!=Color.TRANSPARENT)v.setBackground(shape(background,8));
        v.setClickable(true);
        v.setFocusable(true);
        v.setContentDescription(description);
        v.setOnClickListener(x->action.run());
        return v;
    }
    private void fire(String id){if(id!=null&&!id.isEmpty())callback.send(id);}
    private String mode(){return model.optString("mode","day");}
    private String selectedDate(){return model.optString("date","");}
    private String selectedProvider(){return model.optString("provider","all");}
    private String modeTitle(){
        switch(mode()){
            case "week":return t("Woche","Week");
            case "provider":return t("Behandler","Provider");
            case "service":return t("Behandlung","Service");
            default:return t("Tagesansicht","Day view");
        }
    }
    private String formatted(String iso,String pattern){
        try{
            SimpleDateFormat parser=new SimpleDateFormat("yyyy-MM-dd",Locale.ROOT);
            parser.setLenient(false);parser.setTimeZone(TimeZone.getTimeZone("Europe/Berlin"));
            Date date=parser.parse(iso);
            SimpleDateFormat printer=new SimpleDateFormat(pattern,Locale.GERMANY);
            printer.setTimeZone(TimeZone.getTimeZone("Europe/Berlin"));
            return printer.format(date);
        }catch(Exception ignored){return iso;}
    }
    // Keep the old page opaque and in place while the bridge fetches data.
    // Only the two grid children participate in the arrival transition.
    private void navigate(String action,int direction,View mover) { fire(action); }
    private void fadeNavigate(String action,int direction){navigate(action,direction,animatedPage);}
    View build(){
        FrameLayout outer=new FrameLayout(ctx);
        outer.setBackgroundColor(Color.WHITE);
        LinearLayout page=vertical();
        outer.addView(page,new FrameLayout.LayoutParams(-1,-1));
        buildHeader(page);
        buildDateBar(page);
        dateHost=new FrameLayout(ctx);
        dateHost.setBackgroundColor(Color.WHITE);
        page.addView(dateHost,lp(-1,d(60)));
        renderDateStrip();
        View separator=new View(ctx);separator.setBackgroundColor(LINES);
        page.addView(separator,lp(-1,d(1)));
        timelineHost=new FrameLayout(ctx);
        timelineHost.setBackgroundColor(Color.WHITE);
        timelineHost.setClipChildren(true);
        page.addView(timelineHost,new LinearLayout.LayoutParams(-1,0,1));
        replaceGrid(0,false);
        TextView fab=clickable("+",Color.WHITE,Color.TRANSPARENT,this::showCreationMenu,
            t("Neuen Termin erstellen","New booking"));
        fab.setTextSize(31);
        fab.setBackground(oval(BLUE));fab.setElevation(d(6));
        FrameLayout.LayoutParams fp=new FrameLayout.LayoutParams(d(56),d(56),Gravity.BOTTOM|Gravity.RIGHT);
        fp.rightMargin=d(19);fp.bottomMargin=d(22);
        outer.addView(fab,fp);
        return outer;
    }
    private void renderDateStrip(){
        LinearLayout staging=vertical();
        buildDateStrip(staging);
        View strip=staging.getChildAt(0);
        staging.removeView(strip);
        dateHost.removeAllViews();
        dateHost.addView(strip,new FrameLayout.LayoutParams(-1,-1));
    }
    // Calendar-to-calendar updates never replace the dialog, its inset root,
    // the header, the month controls, or the floating creation action.
    void update(JSONObject next){
        JSONObject nextModel=next.optJSONObject("timeline");
        if(nextModel==null)throw new IllegalArgumentException("Missing calendar timeline");
        String oldDate=selectedDate(),oldMode=mode();
        String oldWeek=array("week").toString();
        String before=model.toString();
        screen=next;model=nextModel;
        headerTitle.setText(t("Kalender","Calendar")+" ("+modeTitle()+")");
        monthLabel.setText(formatted(selectedDate(),"LLLL yyyy"));
        if(!oldDate.equals(selectedDate())||!oldMode.equals(mode())||!oldWeek.equals(array("week").toString()))
            renderDateStrip();
        if(!before.equals(model.toString())){
            int direction=selectedDate().compareTo(oldDate);
            replaceGrid(Integer.signum(direction),oldMode.equals(mode()));
        }
    }
    private void replaceGrid(int direction,boolean preserveScroll){
        int epoch=++generation;
        View previous=gridView;
        int scrollY=preserveScroll&&gridRenderer!=null&&gridRenderer.verticalScroll!=null
            ?gridRenderer.verticalScroll.getScrollY():0;
        int scrollX=preserveScroll&&previous!=null?previous.getScrollX():0;
        // Each outgoing renderer keeps its own immutable timeline snapshot.
        // Cancel interrupted transitions and retain the most recent page only.
        if(previous!=null){
            previous.animate().cancel();previous.setTranslationX(0);previous.setAlpha(1);
        }
        for(int i=timelineHost.getChildCount()-1;i>=0;i--){
            View child=timelineHost.getChildAt(i);
            if(child!=previous){child.animate().cancel();timelineHost.removeViewAt(i);}
        }
        NativeStaffV3Calendar nextRenderer=new NativeStaffV3Calendar(ctx,screen,callback);
        LinearLayout staging=vertical();
        nextRenderer.buildTimeline(staging);
        View incoming=staging.getChildAt(0);
        staging.removeView(incoming);
        incoming.setBackgroundColor(Color.WHITE);
        gridRenderer=nextRenderer;gridView=incoming;animatedPage=incoming;
        int width=timelineHost.getWidth();
        boolean slide=previous!=null&&direction!=0&&width>0;
        if(slide)incoming.setTranslationX(direction*width);
        timelineHost.addView(incoming,new FrameLayout.LayoutParams(-1,-1));
        final View old=previous;
        incoming.getViewTreeObserver().addOnPreDrawListener(new android.view.ViewTreeObserver.OnPreDrawListener(){
            @Override public boolean onPreDraw(){
                if(incoming.getViewTreeObserver().isAlive())incoming.getViewTreeObserver().removeOnPreDrawListener(this);
                if(epoch!=generation)return true;
                nextRenderer.verticalScroll.scrollTo(0,scrollY);
                incoming.scrollTo(scrollX,0);
                if(slide){
                    old.animate().translationX(-direction*width).setDuration(240).start();
                    incoming.animate().translationX(0).setDuration(240).withEndAction(()->{
                        if(epoch==generation&&old.getParent()==timelineHost)timelineHost.removeView(old);
                    }).start();
                }else if(old!=null&&old.getParent()==timelineHost)timelineHost.removeView(old);
                return true;
            }
        });
    }
    private void buildHeader(LinearLayout page){
        LinearLayout header=horizontal();
        header.setBackgroundColor(NAVY);
        TextView menu=clickable("☰",Color.WHITE,Color.TRANSPARENT,this::showNavigation,
            t("Navigation öffnen","Open navigation"));
        header.addView(menu,lp(d(48),d(48)));
        headerTitle=text(t("Kalender","Calendar")+" ("+modeTitle()+")",15,Color.WHITE,true);
        header.addView(headerTitle,new LinearLayout.LayoutParams(0,d(48),1));
        TextView modes=clickable("▦",Color.WHITE,Color.TRANSPARENT,this::showModePicker,
            t("Kalenderansicht ändern","Change calendar view"));
        header.addView(modes,lp(d(46),d(48)));
        TextView filters=clickable("☷",Color.WHITE,Color.TRANSPARENT,this::showFilters,
            t("Filter öffnen","Open filters"));
        header.addView(filters,lp(d(46),d(48)));
        page.addView(header,lp(-1,d(48)));
    }
    private void buildDateBar(LinearLayout page){
        LinearLayout nav=horizontal();
        TextView previous=clickable("‹",INK,Color.TRANSPARENT,
            ()->fadeNavigate("day".equals(mode())?"day-prev":"week-prev",-1),
            t("Vorheriger Zeitraum","Previous period"));
        previous.setTextSize(29);
        nav.addView(previous,lp(d(57),d(52)));
        monthLabel=text(formatted(selectedDate(),"LLLL yyyy"),15,INK,false);
        monthLabel.setGravity(Gravity.CENTER);
        nav.addView(monthLabel,new LinearLayout.LayoutParams(0,d(52),1));
        TextView next=clickable("›",INK,Color.TRANSPARENT,
            ()->fadeNavigate("day".equals(mode())?"day-next":"week-next",1),
            t("Nächster Zeitraum","Next period"));
        next.setTextSize(29);
        nav.addView(next,lp(d(57),d(52)));
        page.addView(nav,lp(-1,d(52)));
    }
    private void buildDateStrip(LinearLayout page){
        SwipeStrip strip=new SwipeStrip(ctx);
        LinearLayout dates=horizontal();
        JSONArray days=array("week");
        for(int i=0;i<days.length();i++){
            String date=days.optString(i);
            LinearLayout cell=vertical();
            cell.setGravity(Gravity.CENTER);
            TextView weekday=text(formatted(date,"EE"),11,INK,false);
            weekday.setGravity(Gravity.CENTER);
            cell.addView(weekday,lp(-1,d(19)));
            boolean highlighted=("week".equals(mode())||date.equals(selectedDate()));
            TextView number=text(formatted(date,"dd"),12,highlighted?Color.WHITE:INK,highlighted);
            number.setGravity(Gravity.CENTER);
            if(highlighted)number.setBackground(oval(PINK));
            LinearLayout.LayoutParams numberParams=lp(d(33),d(33));
            numberParams.gravity=Gravity.CENTER;
            cell.addView(number,numberParams);
            cell.setContentDescription(formatted(date,"EEEE dd MMMM yyyy"));
            cell.setOnClickListener(v->{if(!selectedDate().equals(date))
                fadeNavigate("date:"+date,date.compareTo(selectedDate())>0?1:-1);});
            dates.addView(cell,new LinearLayout.LayoutParams(0,d(60),1));
        }
        strip.addView(dates,new LinearLayout.LayoutParams(-1,d(60)));
        strip.setOnSwipe(direction->navigate(direction>0?"week-next":"week-prev",direction,strip));
        page.addView(strip,lp(-1,d(60)));
    }
    private void buildTimeline(LinearLayout page){
        HorizontalScrollView horizontal=new HorizontalScrollView(ctx) {
            @Override public boolean onInterceptTouchEvent(MotionEvent event) {
                // A one-column day grid uses a native follow-finger date swipe;
                // it must not be stolen by a non-scrollable horizontal container.
                if("day".equals(mode()))return false;
                return super.onInterceptTouchEvent(event);
            }
            @Override public boolean onTouchEvent(MotionEvent event) {
                return !"day".equals(mode()) && super.onTouchEvent(event);
            }
        };
        horizontal.setHorizontalScrollBarEnabled(false);
        horizontal.setFillViewport(true);
        LinearLayout inner=vertical();
        JSONArray cols=array("columns");
        int screenWidth=ctx.getResources().getDisplayMetrics().widthPixels;
        int colWidth="day".equals(mode())?Math.max(d(190),screenWidth-rulerWidth):d(165);
        int wholeWidth=rulerWidth+cols.length()*colWidth;
        LinearLayout heading=horizontal();
        TextView blank=text("",11,INK,false);
        heading.addView(blank,lp(rulerWidth,d(39)));
        for(int i=0;i<cols.length();i++){
            JSONObject col=at(cols,i);
            String label="week".equals(mode())?formatted(str(col,"date"),"EEE dd.MM")
                : "day".equals(mode())?formatted(selectedDate(),"EEEE dd.MM.yyyy")
                :str(col,"title");
            TextView v=text(label,12,INK,true);
            v.setGravity(Gravity.CENTER);
            heading.addView(v,lp(colWidth,d(39)));
        }
        inner.addView(heading,lp(wholeWidth,d(39)));
        ScrollView vertical=new ScrollView(ctx);
        verticalScroll=vertical;
        vertical.setFillViewport(false);
        vertical.setVerticalScrollBarEnabled(false);
        LinearLayout grid=horizontal();
        grid.setGravity(Gravity.TOP);
        grid.addView(new RulerView(ctx),lp(rulerWidth,(hourEnd-hourStart)*hourHeight));
        for(int i=0;i<cols.length();i++){
            final int index=i;
            JSONObject col=at(cols,i);
            TimeColumn view=new TimeColumn(ctx,index,col,colWidth);
            grid.addView(view,lp(colWidth,(hourEnd-hourStart)*hourHeight));
        }
        vertical.addView(grid,new ScrollView.LayoutParams(wholeWidth,(hourEnd-hourStart)*hourHeight));
        inner.addView(vertical,new LinearLayout.LayoutParams(wholeWidth,0,1));
        horizontal.addView(inner,new HorizontalScrollView.LayoutParams(wholeWidth,-1));
        page.addView(horizontal,new LinearLayout.LayoutParams(-1,0,1));
        animatedPage=horizontal;
    }
    private void showModePicker(){
        String[] names={t("Tagesansicht","Day view"),t("Woche","Week"),
            t("Behandler","Provider"),t("Behandlung","Service")};
        String[] ids={"day","week","provider","service"};
        new AlertDialog.Builder(ctx)
            .setTitle(t("Kalenderansicht","Calendar view"))
            .setItems(names,(d,index)->fire("cal-mode:"+ids[index]))
            .setNegativeButton(t("Abbrechen","Cancel"),null).show();
    }
    private void showNavigation(){
        String[] labels={t("Übersicht","Home"),t("Kalender","Calendar"),
            t("Patienten","Patients"),"Office",t("Einstellungen","Settings")};
        String[] ids={"home","calendar","patients","office","settings"};
        new AlertDialog.Builder(ctx).setTitle("A+ ESTHETIC")
            .setItems(labels,(d,index)->fire(ids[index]))
            .setNegativeButton(t("Schließen","Close"),null).show();
    }
    private void showFilters(){
        String[] names={t("Behandler","Provider"),t("Behandlung","Service"),
            t("Heute","Today"),t("Arbeitszeiten","Availability")};
        new AlertDialog.Builder(ctx).setTitle(t("Filter","Filter"))
            .setItems(names,(d,which)->{
                if(which==2){fire("cal-today");return;}
                if(which==3){fire("availability");return;}
                boolean provider=which==0;
                JSONArray choices=array(provider?"providers":"services");
                String[] labels=new String[choices.length()+1];
                String[] ids=new String[labels.length];
                labels[0]=t("Alle","All");ids[0]="all";
                for(int i=0;i<choices.length();i++){
                    JSONObject row=at(choices,i);
                    labels[i+1]=str(row,"label");ids[i+1]=str(row,"id");
                }
                new AlertDialog.Builder(ctx).setTitle(names[which])
                    .setItems(labels,(dialog,index)->fire((provider?"cal-provider:":"cal-service:")+ids[index]))
                    .setNegativeButton(t("Abbrechen","Cancel"),null).show();
            }).setNegativeButton(t("Fertig","Done"),null).show();
    }
    private void showCreationMenu(){
        String[] names={t("Termin buchen","Add booking"),t("Notiz / Sperrzeit","Note / Block"),
            t("Arbeitszeiten","Availability")};
        String[] ids={"new-appointment","new-block","availability"};
        String[] descriptions={t("Neue Buchung erstellen","Create a booking"),t("Kalenderzeit reservieren","Reserve calendar time"),t("Verfügbarkeit bearbeiten","Edit availability")};
        String[] glyphs={"+","▤","◷"}; int[] colors={PINK,BLUE,NAVY};
        Dialog menu=new Dialog(ctx);menu.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel=new LinearLayout(ctx);panel.setOrientation(LinearLayout.VERTICAL);panel.setBackgroundColor(Color.WHITE);
        LinearLayout header=new LinearLayout(ctx);header.setGravity(Gravity.CENTER_VERTICAL);header.setBackgroundColor(NAVY);header.setPadding(d(16),0,d(8),0);
        TextView title=text(t("Hinzufügen","Add"),17,Color.WHITE,true);header.addView(title,new LinearLayout.LayoutParams(0,d(50),1));title.setGravity(Gravity.CENTER_VERTICAL);
        TextView close=text("×",25,Color.WHITE,false);close.setGravity(Gravity.CENTER);close.setContentDescription(t("Schließen","Close"));close.setOnClickListener(v->menu.dismiss());header.addView(close,lp(d(44),d(50)));panel.addView(header);
        for(int i=0;i<ids.length;i++){
            final String id=ids[i];LinearLayout entry=new LinearLayout(ctx);entry.setGravity(Gravity.CENTER_VERTICAL);entry.setPadding(d(14),d(12),d(14),d(12));
            TextView glyph=text(glyphs[i],23,Color.WHITE,true);glyph.setGravity(Gravity.CENTER);GradientDrawable tile=new GradientDrawable();tile.setColor(colors[i]);tile.setCornerRadius(d(9));glyph.setBackground(tile);entry.addView(glyph,lp(d(42),d(42)));
            LinearLayout copy=new LinearLayout(ctx);copy.setOrientation(LinearLayout.VERTICAL);copy.setPadding(d(14),0,d(8),0);copy.addView(text(names[i],16,INK,true));copy.addView(text(descriptions[i],12,MUTED,false));entry.addView(copy,new LinearLayout.LayoutParams(0,-2,1));entry.addView(text("›",22,MUTED,false));
            entry.setOnClickListener(v->{menu.dismiss();fire(id);});entry.setFocusable(true);panel.addView(entry,lp(-1,-2));
            if(i<ids.length-1){View line=new View(ctx);line.setBackgroundColor(LINES);panel.addView(line,lp(-1,d(1)));}
        }
        menu.setContentView(panel);menu.show();Window window=menu.getWindow();if(window!=null){window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));window.setLayout(Math.min(d(360),ctx.getResources().getDisplayMetrics().widthPixels-d(32)),-2);window.setGravity(Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);android.view.WindowManager.LayoutParams attrs=window.getAttributes();attrs.y=d(18);window.setAttributes(attrs);}
    }

    private final class RulerView extends View {
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        RulerView(Context ctx){super(ctx);setBackgroundColor(RULER);}
        @Override protected void onDraw(Canvas canvas){
            super.onDraw(canvas);
            paint.setColor(MUTED);paint.setTextSize(d(10));paint.setTypeface(Typeface.DEFAULT);
            paint.setTextAlign(Paint.Align.RIGHT);
            for(int hour=hourStart;hour<hourEnd;hour++){
                float y=(hour-hourStart)*hourHeight;
                canvas.drawText(String.format(Locale.ROOT,"%02d:00",hour),getWidth()-d(7),y+d(12),paint);
            }
        }
    }
    private final class TimeColumn extends View {
        private final int index;
        private final JSONObject column;
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        private final ArrayList<TouchTarget> hitTargets=new ArrayList<>();
        private float downX,downY;
        private boolean draggingHorizontal;
        private boolean consumingGesture;
        private float lastDelta;
        private final int columnWidth;
        TimeColumn(Context context,int index,JSONObject column,int width){
            super(context);
            this.index=index;this.column=column;this.columnWidth=width;
            setLayerType(View.LAYER_TYPE_SOFTWARE,null);
            setBackgroundColor(Color.WHITE);
            setClickable(true);
            setContentDescription(t("Zeitplan","Schedule"));
        }
        private float yFor(int min){return ((float)min-hourStart*60)*hourHeight/60f;}
        private int minute(JSONObject row,String key){return row.optInt(key,0);}
        private void fill(Canvas c,int color,float left,float top,float right,float bottom,float radius){
            paint.setColor(color);paint.setStyle(Paint.Style.FILL);
            c.drawRoundRect(new RectF(left,top,right,bottom),radius,radius,paint);
        }
        private void label(Canvas c,String value,float x,float y,float maxWidth,float size,boolean bold,int maxLines){
            if(value==null||value.isEmpty())return;
            paint.setColor(INK);paint.setTypeface(bold?Typeface.create("sans-serif-medium",Typeface.NORMAL):Typeface.DEFAULT);
            paint.setTextSize(d(size));paint.setTextAlign(Paint.Align.LEFT);
            // Avoid overflowing neighboring lanes; truncate by measured glyph width.
            String[] words=value.replace('\n',' ').split("\\s+");
            String line="";int lines=0;
            for(String word:words){
                String next=line.isEmpty()?word:line+" "+word;
                if(paint.measureText(next)>Math.max(15,maxWidth)&&!line.isEmpty()){
                    paint.setTextScaleX(Math.min(1f,Math.max(1,maxWidth)/Math.max(1,paint.measureText(line))));c.drawText(line,x,y+lines*d(size+3),paint);paint.setTextScaleX(1f);
                    lines++;line=word;
                    if(lines>=maxLines)return;
                }else line=next;
            }
            if(lines<maxLines){paint.setTextScaleX(Math.min(1f,Math.max(1,maxWidth)/Math.max(1,paint.measureText(line))));c.drawText(line,x,y+lines*d(size+3),paint);paint.setTextScaleX(1f);}
        }
        @Override protected void onDraw(Canvas canvas){
            super.onDraw(canvas);
            hitTargets.clear();
            float w=getWidth();
            for(int hour=0;hour<=hourEnd-hourStart;hour++){
                float y=hour*hourHeight;
                paint.setColor(LINES);paint.setStrokeWidth(d(.65f));
                canvas.drawLine(0,y,w,y,paint);
            }
            for(int quarter=1;quarter<(hourEnd-hourStart)*4;quarter++){
                paint.setColor(Color.argb(85,200,208,216));
                canvas.drawLine(0,quarter*hourHeight/4f,w,quarter*hourHeight/4f,paint);
            }
            JSONArray available=array("bands");
            for(int i=0;i<available.length();i++){
                JSONObject b=at(available,i);
                if(b.optInt("column",-1)!=index)continue;
                float start=yFor(b.optInt("lower")),end=yFor(b.optInt("upper"));
                fill(canvas,PALE,0,start,w,end,0);
            }
            JSONArray all=array("events");
            for(int i=0;i<all.length();i++){
                JSONObject event=at(all,i);
                if(event.optInt("column",-1)!=index)continue;
                int start=event.optInt("lower"),end=event.optInt("upper");
                float y=yFor(start);
                float h=Math.max(d(25),yFor(end)-y);
                int lanes=Math.max(1,event.optInt("lanes",1));
                int lane=event.optInt("lane",0);
                float laneWidth=w/lanes;
                float left=lane*laneWidth+d(1);
                float right=(lane+1)*laneWidth-d(1);
                int color=AMBER;
                String kind=str(event,"kind");
                if("note".equals(kind))color=Color.rgb(255,214,133);
                if("block".equals(kind))color=Color.rgb(227,171,91);
                fill(canvas,color,left,y+1,right,y+h-1,d(2));
                String title=str(event,"title");
                String detail=str(event,"detail");
                String time=str(event,"start");
                float tx=left+d(5),labelWidth=right-left-d(10);
                if(h>=d(27))label(canvas,title,tx,y+d(17),labelWidth,11,true,h>=d(60)?2:1);
                if(h>=d(56))label(canvas,time,tx,y+h-d(17),labelWidth,10,false,1);
                if(h>=d(86))label(canvas,detail,tx,y+d(52),labelWidth,10,false,1);
                String id=str(event,"id");
                if(!id.isEmpty())hitTargets.add(new TouchTarget(new RectF(left,y,right,y+h),id));
            }
            paint.setColor(LINES);canvas.drawLine(0,0,0,getHeight(),paint);
        }
        @Override public boolean onTouchEvent(MotionEvent e){
            switch(e.getActionMasked()){
                case MotionEvent.ACTION_DOWN:
                    downX=e.getX();downY=e.getY();lastDelta=0;
                    draggingHorizontal=false;consumingGesture=false;
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx=e.getX()-downX,dy=e.getY()-downY;
                    if(!draggingHorizontal && Math.abs(dx)>d(14) && Math.abs(dx)>Math.abs(dy)*1.45f){
                        draggingHorizontal=true;
                        if("day".equals(mode()))getParent().requestDisallowInterceptTouchEvent(true);
                    }
                    if(draggingHorizontal&&"day".equals(mode())){
                        consumingGesture=true;
                        lastDelta=Math.max(-d(185),Math.min(d(185),dx));
                        setTranslationX(lastDelta);
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP:{
                    float dx=e.getX()-downX,dy=e.getY()-downY;
                    if("day".equals(mode())&&draggingHorizontal&&Math.abs(dx)>d(60)&&
                        Math.abs(dx)>Math.abs(dy)*1.4f){
                        int dir=dx<0?1:-1;
                        // Keep the outgoing grid readable until the fetched
                        // adjacent page is ready; never fade the calendar out.
                        animate().translationX(0).alpha(1).setDuration(140).start();
                        fire(dir>0?"day-next":"day-prev");
                        return true;
                    }
                    animate().translationX(0).alpha(1).setDuration(145).start();
                    if(Math.abs(dx)<d(12)&&Math.abs(dy)<d(12)){
                        float px=e.getX(),py=e.getY();
                        for(TouchTarget target:hitTargets)if(target.bounds.contains(px,py)){
                            fire(target.action);return true;
                        }
                        int minutes=hourStart*60+Math.max(0,(int)(py/hourHeight*60f));
                        minutes=Math.min(hourEnd*60-30,(minutes/30)*30);
                        String time=String.format(Locale.ROOT,"%02d:%02d",minutes/60,minutes%60);
                        String date=str(column,"date");
                        String staff="provider".equals(mode())?str(column,"ref"):selectedProvider();
                        fire("slot:"+date+":"+time+":"+staff);
                    }
                    return true;
                }
                case MotionEvent.ACTION_CANCEL:
                    animate().translationX(0).alpha(1).setDuration(145).start();
                    return true;
            }
            return true;
        }
    }
    private static final class TouchTarget{
        final RectF bounds;final String action;
        TouchTarget(RectF bounds,String action){this.bounds=bounds;this.action=action;}
    }
    private final class SwipeStrip extends LinearLayout {
        interface Swipe{void release(int direction);}
        private Swipe swipe;
        private float downX,downY;
        private boolean sliding;
        SwipeStrip(Context context){super(context);setOrientation(HORIZONTAL);}
        void setOnSwipe(Swipe action){swipe=action;}
        @Override public boolean onInterceptTouchEvent(MotionEvent e){
            if(e.getActionMasked()==MotionEvent.ACTION_DOWN){
                downX=e.getX();downY=e.getY();sliding=false;
            } else if(e.getActionMasked()==MotionEvent.ACTION_MOVE){
                if(Math.abs(e.getX()-downX)>d(14)&&
                   Math.abs(e.getX()-downX)>Math.abs(e.getY()-downY)*1.4f){
                    sliding=true;return true;
                }
            }
            return super.onInterceptTouchEvent(e);
        }
        @Override public boolean onTouchEvent(MotionEvent e){
            if(!sliding)return super.onTouchEvent(e);
            if(e.getActionMasked()==MotionEvent.ACTION_MOVE){
                if(getChildCount()>0)getChildAt(0).setTranslationX(
                    Math.max(-d(130),Math.min(d(130),e.getX()-downX)));
                return true;
            }
            if(e.getActionMasked()==MotionEvent.ACTION_UP){
                float dx=e.getX()-downX;
                if(Math.abs(dx)>d(55)&&swipe!=null){
                    if(getChildCount()>0)getChildAt(0).animate().translationX(0)
                        .setDuration(175).start();
                    swipe.release(dx<0?1:-1);
                }else if(getChildCount()>0){
                    getChildAt(0).animate().translationX(0).setDuration(160).start();
                }
                sliding=false;return true;
            }
            if(e.getActionMasked()==MotionEvent.ACTION_CANCEL){
                if(getChildCount()>0)getChildAt(0).animate().translationX(0).setDuration(160).start();
                sliding=false;return true;
            }
            return true;
        }
    }
}

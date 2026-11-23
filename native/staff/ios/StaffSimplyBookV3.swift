// A+ Esthetic V3: reference-matched native SimplyBook-style calendar.
// Isolated from V2; retains existing authenticated Book read/write actions.
// Native UI owns no patient data, booking state or credentials.
import SwiftUI

struct StaffSimplyBookV3: View {
    @ObservedObject var state: StaffScreenState
    let model: [String: Any]

    @State private var showNavigation = false
    @State private var showFilters = false
    @State private var showActions = false
    @State private var showViewModes = false
    @State private var slideForward = true
    @State private var releasedSwipe: CGFloat = 0
    @GestureState private var liveSwipe: CGFloat = 0

    private let navy = Color(red: 32/255, green: 43/255, blue: 61/255)
    private let pink = Color(red: 249/255, green: 27/255, blue: 82/255)
    private let amber = Color(red: 255/255, green: 190/255, blue: 103/255)
    private let blue = Color(red: 0/255, green: 153/255, blue: 200/255)
    private let rule = Color(red: 220/255, green: 226/255, blue: 234/255)
    private let rulerFill = Color(red: 246/255, green: 247/255, blue: 251/255)
    private let ink = Color(red: 42/255, green: 48/255, blue: 58/255)

    private let rulerWidth: CGFloat = 56
    private let hourHeight: CGFloat = 82
    private let referenceWeekColumnWidth: CGFloat = 165
    private var firstHour: Int { model["firstHour"] as? Int ?? 10 }
    private var lastHour: Int { model["lastHour"] as? Int ?? 20 }
    private var hourCount: Int { max(1,lastHour-firstHour) }
    private var firstMinute: Int { firstHour*60 }
    private func navigate(_ action: String, forward: Bool) {
        slideForward = forward
        fire(action)
    }
    private func navigateTo(_ day: String) {
        navigate("date:"+day, forward: day >= selectedDate)
    }
    private func swipeGesture(weekNavigation: Bool) -> some Gesture {
        DragGesture(minimumDistance: 18)
            .updating($liveSwipe) { drag, value, _ in
                if abs(drag.translation.width) > abs(drag.translation.height) * 1.25 {
                    value = max(-220,min(220,drag.translation.width))
                }
            }
            .onEnded { drag in
                let dx = drag.translation.width
                guard abs(dx)>75, abs(dx)>abs(drag.translation.height)*1.4 else {
                    withAnimation(.interactiveSpring(response:0.25,dampingFraction:0.8)) { releasedSwipe=0 }
                    return
                }
                let forward=dx < 0
                withAnimation(.easeOut(duration:0.16)) { releasedSwipe = forward ? -72 : 72 }
                navigate(weekNavigation ? (forward ? "week-next":"week-prev")
                                        : (forward ? "day-next":"day-prev"), forward:forward)
            }
    }

    private var mode: String { model["mode"] as? String ?? "day" }
    private var selectedDate: String { model["date"] as? String ?? "" }
    private var week: [String] { model["week"] as? [String] ?? [] }
    private var columns: [[String: Any]] { model["columns"] as? [[String: Any]] ?? [] }
    private var events: [[String: Any]] { model["events"] as? [[String: Any]] ?? [] }
    private var bands: [[String: Any]] { model["bands"] as? [[String: Any]] ?? [] }
    private var providers: [[String: Any]] { model["providers"] as? [[String: Any]] ?? [] }
    private var services: [[String: Any]] { model["services"] as? [[String: Any]] ?? [] }
    private var selectedProvider: String { model["provider"] as? String ?? "all" }
    private var selectedService: String { model["service"] as? String ?? "all" }
    private var english: Bool { model["language"] as? String == "en" }

    private func t(_ de: String, _ en: String) -> String { english ? en : de }
    private func text(_ row: [String: Any], _ key: String) -> String { row[key] as? String ?? "" }
    private func number(_ row: [String: Any], _ key: String) -> Int {
        if let n = row[key] as? NSNumber { return n.intValue }
        return row[key] as? Int ?? 0
    }
    private func fire(_ action: String) { state.send?(action, [:]) }

    private func formatDate(_ raw: String, _ pattern: String) -> String {
        let input = DateFormatter()
        input.locale = Locale(identifier: "en_US_POSIX")
        input.timeZone = TimeZone(identifier: "Europe/Berlin")
        input.dateFormat = "yyyy-MM-dd"
        guard let date = input.date(from: raw) else { return raw }
        let output = DateFormatter()
        output.locale = Locale(identifier: english ? "en_GB" : "de_DE")
        output.timeZone = input.timeZone
        output.dateFormat = pattern
        return output.string(from: date)
    }
    private var monthTitle: String { formatDate(selectedDate, "LLLL yyyy") }
    private var modeName: String {
        switch mode {
        case "week": return t("Woche", "Week")
        case "provider": return t("Behandler", "Provider")
        case "service": return t("Behandlung", "Service")
        default: return t("Tagesansicht", "Day view")
        }
    }

    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 0) {
                topBar
                dateNavigator
                dateStrip
                Rectangle().fill(rule).frame(height: 0.6)
                ZStack {
                    timeline(availableWidth: geometry.size.width)
                        .id(selectedDate+"-"+mode)
                        .transition(.asymmetric(
                            insertion:.move(edge:slideForward ? .trailing : .leading).combined(with:.opacity),
                            removal:.move(edge:slideForward ? .leading : .trailing).combined(with:.opacity)
                        ))
                        .offset(x:liveSwipe+releasedSwipe)
                }
                .clipped()
                .animation(.easeInOut(duration:0.34),value:selectedDate)
                .animation(.easeInOut(duration:0.34),value:mode)
                .onChange(of: selectedDate) { _ in
                    withAnimation(.easeInOut(duration:0.34)) { releasedSwipe=0 }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(.white)
            .overlay(alignment: .bottomTrailing) {
                Button { showActions = true } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 26, weight: .medium))
                        .foregroundStyle(.white)
                        .frame(width: 54, height: 54)
                        .background(blue, in: Circle())
                        .shadow(color: .black.opacity(0.26), radius: 5, x: 0, y: 3)
                }
                .accessibilityLabel(t("Neuen Termin erstellen", "New booking"))
                .padding(.trailing, 18)
                .padding(.bottom, 22)
            }
            .confirmationDialog(t("Hinzufügen", "Add"), isPresented: $showActions, titleVisibility: .visible) {
                Button(t("Termin buchen", "Add booking")) { fire("new-appointment") }
                Button(t("Notiz / Sperrzeit", "Note / Block")) { fire("new-block") }
                Button(t("Arbeitszeiten", "Availability")) { fire("availability") }
                Button(t("Abbrechen", "Cancel"), role: .cancel) { }
            }
            .confirmationDialog(t("Kalenderansicht", "Calendar view"), isPresented: $showViewModes, titleVisibility: .visible) {
                Button(t("Tagesansicht", "Day view")) { fire("cal-mode:day") }
                Button(t("Woche", "Week")) { fire("cal-mode:week") }
                Button(t("Behandler", "Provider")) { fire("cal-mode:provider") }
                Button(t("Behandlung", "Service")) { fire("cal-mode:service") }
                Button(t("Abbrechen", "Cancel"), role: .cancel) { }
            }
            .sheet(isPresented: $showFilters) { filterSheet }
            .sheet(isPresented: $showNavigation) { navigationSheet }
            .preferredColorScheme(.light)
        }
    }

    private var topBar: some View {
        HStack(spacing: 0) {
            Button { showNavigation = true } label: {
                Image(systemName: "line.3.horizontal")
                    .font(.system(size: 18, weight: .medium))
                    .frame(width: 44, height: 48)
            }
            .accessibilityLabel(t("Navigation öffnen", "Open navigation"))
            Text("Kalender (\(modeName))")
                .font(.system(size: 15, weight: .semibold))
                .lineLimit(1)
                .padding(.leading, 5)
            Spacer(minLength: 0)
            Button { showViewModes = true } label: {
                Image(systemName: "calendar")
                    .font(.system(size: 19, weight: .regular))
                    .frame(width: 44, height: 48)
            }
            .accessibilityLabel(t("Kalenderansicht ändern", "Change calendar view"))
            Button { showFilters = true } label: {
                Image(systemName: "line.3.horizontal.decrease")
                    .font(.system(size: 19))
                    .rotationEffect(.degrees(180))
                    .frame(width: 44, height: 48)
            }
            .accessibilityLabel(t("Filter öffnen", "Open filters"))
        }
        .foregroundStyle(.white)
        .background(navy)
    }

    private var dateNavigator: some View {
        HStack(spacing: 0) {
            Button { navigate(mode == "day" ? "day-prev" : "week-prev",forward:false) } label: {
                Image(systemName: "chevron.left")
                    .font(.system(size: 17, weight: .medium))
                    .frame(width: 56, height: 53)
            }
            Spacer(minLength: 0)
            Text(monthTitle)
                .font(.system(size: 15, weight: .regular))
                .foregroundStyle(ink)
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 0)
            Button { navigate(mode == "day" ? "day-next" : "week-next",forward:true) } label: {
                Image(systemName: "chevron.right")
                    .font(.system(size: 17, weight: .medium))
                    .frame(width: 56, height: 53)
            }
        }
        .foregroundStyle(ink)
        .background(.white)
    }

    private var dateStrip: some View {
        HStack(spacing: 0) {
            ForEach(Array(week.enumerated()), id: \.offset) { _, day in
                let active = mode == "week" || day == selectedDate
                Button {
                    if day != selectedDate { navigateTo(day) }
                } label: {
                    VStack(spacing: 5) {
                        Text(formatDate(day, "EE"))
                            .font(.system(size: 12, weight: .regular))
                            .foregroundStyle(ink.opacity(0.85))
                        Text(formatDate(day, "dd"))
                            .font(.system(size: 12, weight: active ? .medium : .regular))
                            .foregroundStyle(active ? .white : ink.opacity(0.82))
                            .frame(maxWidth: .infinity)
                            .frame(height: 32)
                            .background(active ? pink : Color.clear,
                                        in: mode == "week" ? AnyShape(Capsule()) : AnyShape(Circle()))
                    }
                    .frame(maxWidth: .infinity)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(formatDate(day, "EEEE dd MMMM yyyy"))
                .accessibilityAddTraits(day == selectedDate ? [.isSelected] : [])
            }
        }
        .padding(.horizontal, 10)
        .padding(.bottom, 6)
        .background(.white)
        .simultaneousGesture(swipeGesture(weekNavigation:true))
    }

    private func timeline(availableWidth: CGFloat) -> some View {
        let width: CGFloat = mode == "day"
            ? max(200, availableWidth - rulerWidth)
            : referenceWeekColumnWidth
        return ScrollView(.horizontal, showsIndicators: mode != "day") {
            VStack(spacing: 0) {
                HStack(spacing: 0) {
                    Color.clear.frame(width: rulerWidth, height: 39)
                    ForEach(Array(columns.enumerated()), id: \.offset) { _, col in
                        Text(columnHeading(col))
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(ink)
                            .frame(width: width, height: 39)
                            .overlay(alignment: .leading) { Rectangle().fill(rule).frame(width: 0.6) }
                    }
                }
                .background(.white)
                Rectangle().fill(rule).frame(height: 0.6)
                ScrollView(.vertical, showsIndicators: false) {
                        HStack(alignment: .top, spacing: 0) {
                            hourRuler
                            ForEach(Array(columns.enumerated()), id: \.offset) { index, column in
                                gridColumn(index: index, column: column, width: width)
                            }
                        }
                        .frame(height: hourHeight * CGFloat(hourCount), alignment: .top)
                    }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(.white)
        // In weekly/provider views the grid must scroll horizontally through
        // columns; only the sticky date strip changes weeks via a swipe.
        .simultaneousGesture(swipeGesture(weekNavigation:false),
                             including:mode == "day" ? .all : .none)
    }

    private func columnHeading(_ column: [String: Any]) -> String {
        if mode == "week" {
            return formatDate(text(column, "date"), "dd-MM-yyyy")
        }
        if mode == "day" {
            return formatDate(selectedDate, "EEEE, dd-MM-yyyy")
        }
        return text(column, "title")
    }

    private var hourRuler: some View {
        VStack(spacing: 0) {
            ForEach(firstHour..<lastHour, id: \.self) { hour in
                Text(String(format: "%02d:00", hour))
                    .font(.system(size: 10, weight: .regular))
                    .foregroundStyle(ink.opacity(0.58))
                    .frame(width: rulerWidth - 6, height: hourHeight, alignment: .topTrailing)
                    .padding(.trailing, 5)
                    .id("ruler-\(String(format: "%02d", hour))")
            }
        }
        .frame(width: rulerWidth)
        .background(rulerFill)
    }

    private func gridColumn(index: Int, column: [String: Any], width: CGFloat) -> some View {
        ZStack(alignment: .topLeading) {
            Color.white
            ForEach(0..<hourCount, id: \.self) { hour in
                Rectangle().fill(rule).frame(height: 0.7)
                    .offset(y: CGFloat(hour) * hourHeight)
                    .allowsHitTesting(false)
            }
            ForEach(0..<(hourCount*4), id: \.self) { quarter in
                Rectangle().fill(rule.opacity(0.36)).frame(height: 0.4)
                    .offset(y: CGFloat(quarter) * hourHeight / 4)
                    .allowsHitTesting(false)
            }
            ForEach(Array(bands.filter { number($0,"column") == index }.enumerated()), id: \.offset) { _, band in
                Rectangle().fill(Color(red: 1, green: 0.98, blue: 0.92))
                    .frame(height: CGFloat(max(0, number(band,"upper") - number(band,"lower"))) * hourHeight / 60)
                    .offset(y: CGFloat(number(band,"lower")-firstMinute) * hourHeight / 60)
                    .allowsHitTesting(false)
            }
            ForEach(0..<(hourCount*2), id: \.self) { slot in
                let slotTime = String(format: "%02d:%02d", firstHour+slot/2, (slot%2)*30)
                Button {
                    let staff = mode == "provider" ? text(column, "ref") : selectedProvider
                    fire("slot:" + text(column, "date") + ":" + slotTime + ":" + staff)
                } label: {
                    Color.clear.frame(width: width, height: hourHeight / 2)
                }
                .buttonStyle(.plain)
                .offset(y: CGFloat(slot) * hourHeight / 2)
                .accessibilityLabel(t("Zeit", "Time") + " " + slotTime)
            }
            ForEach(Array(events.filter { number($0,"column") == index }.enumerated()), id: \.offset) { _, event in
                appointmentBlock(event, columnWidth: width)
            }
            Rectangle().fill(rule).frame(width: 0.6)
                .frame(maxWidth: .infinity, alignment: .leading)
                .allowsHitTesting(false)
        }
        .frame(width: width, height: hourHeight * CGFloat(hourCount))
        .clipped()
    }

    private func appointmentBlock(_ event: [String: Any], columnWidth: CGFloat) -> some View {
        let start = number(event,"lower")
        let finish = number(event,"upper")
        let laneCount = max(number(event,"lanes"),1)
        let lane = number(event,"lane")
        let width = columnWidth / CGFloat(laneCount)
        let height = max(25, CGFloat(max(1,finish-start)) * hourHeight / 60)
        let kind = text(event,"kind")
        let isNote = kind == "note"
        let title = text(event,"title")
        let time = text(event,"start") + " - " + text(event,"end")
        return Button {
            let id = text(event,"id")
            if !id.isEmpty { fire(id) }
        } label: {
            VStack(spacing: 4) {
                Text(title)
                    .font(.system(size: 11, weight: .semibold))
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                if height > 39 {
                    Text(time == " - " ? text(event,"detail") : time)
                        .font(.system(size: 9, weight: .regular))
                        .lineLimit(1)
                }
                if isNote && height > 70 {
                    Text(t("Notiz", "Note"))
                        .font(.system(size: 9))
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(ink)
            .padding(.top, 6)
            .frame(width: max(16,width-1), height: height)
            .background(amber)
            .overlay(Rectangle().stroke(.white.opacity(0.55), lineWidth: 0.6))
        }
        .buttonStyle(.plain)
        .offset(x: CGFloat(lane) * width, y: CGFloat(start-firstMinute) * hourHeight / 60)
        .accessibilityLabel(title+" "+time)
    }

    private var filterSheet: some View {
        NavigationView {
            List {
                Section(t("Behandler", "Provider")) {
                    Button(t("Alle", "All")) { showFilters=false;fire("cal-provider:all") }
                    ForEach(Array(providers.enumerated()), id: \.offset) { _, item in
                        Button(text(item,"label")) {
                            showFilters=false
                            fire("cal-provider:"+text(item,"id"))
                        }
                    }
                }
                Section(t("Behandlung", "Service")) {
                    Button(t("Alle", "All")) { showFilters=false;fire("cal-service:all") }
                    ForEach(Array(services.enumerated()), id: \.offset) { _, item in
                        Button(text(item,"label")) {
                            showFilters=false
                            fire("cal-service:"+text(item,"id"))
                        }
                    }
                }
                Section {
                    Button(t("Zum heutigen Tag", "Today")) {
                        showFilters=false
                        fire("cal-today")
                    }
                    Button(t("Arbeitszeiten", "Availability")) {
                        showFilters=false
                        fire("availability")
                    }
                }
            }
            .navigationTitle(t("Filter", "Filter"))
            .navigationBarItems(trailing: Button(t("Fertig", "Done")) { showFilters=false })
        }
        
    }

    private var navigationSheet: some View {
        NavigationView {
            List {
                Button(t("Übersicht", "Home")) { showNavigation=false;fire("home") }
                Button(t("Kalender", "Calendar")) { showNavigation=false;fire("calendar") }
                Button(t("Patienten", "Patients")) { showNavigation=false;fire("patients") }
                Button("Office") { showNavigation=false;fire("office") }
                Button(t("Einstellungen", "Settings")) { showNavigation=false;fire("settings") }
            }
            .navigationTitle("A+ ESTHETIC")
            .navigationBarItems(trailing: Button(t("Schließen", "Close")) { showNavigation=false })
        }
        
    }
}

// A shape-eraser avoids view-type ambiguity between Capsule and Circle.
private struct AnyShape: Shape {
    private let draw: (CGRect) -> Path
    init<S: Shape>(_ shape: S) { draw = { rect in shape.path(in: rect) } }
    func path(in rect: CGRect) -> Path { draw(rect) }
}

// A+ Esthetic native time-grid calendar — SimplyBook-style interaction model.
// The only data source is the existing authenticated Book API via native-workspace.mjs.
// No web view, no independent patient store and no direct database mutations.
import SwiftUI

struct StaffCalendarTimeline: View {
    @ObservedObject var state: StaffScreenState
    let model: [String: Any]

    @State private var didInitialScroll = false

    private let accent = Color(red: 0.16, green: 0.40, blue: 0.57)
    private let background = Color(red: 0.98, green: 0.985, blue: 0.985)
    private let stroke = Color(red: 0.86, green: 0.89, blue: 0.91)
    private let muted = Color(red: 0.45, green: 0.49, blue: 0.52)
    private let hourHeight: CGFloat = 64
    private let rulerWidth: CGFloat = 45

    private var mode: String { model["mode"] as? String ?? "day" }
    private var selectedDate: String { model["date"] as? String ?? "" }
    private var selectedProvider: String { model["provider"] as? String ?? "all" }
    private var selectedService: String { model["service"] as? String ?? "all" }
    private var english: Bool { model["language"] as? String == "en" }
    private func tr(_ german: String, _ englishText: String) -> String { english ? englishText : german }
    private func text(_ item: [String: Any], _ key: String) -> String { item[key] as? String ?? "" }
    private func items(_ key: String) -> [[String: Any]] { model[key] as? [[String: Any]] ?? [] }
    private func value(_ item: [String: Any], _ key: String) -> Int {
        if let number = item[key] as? NSNumber { return number.intValue }
        return item[key] as? Int ?? 0
    }
    private func move(_ key: String) { state.send?(key, [:]) }

    private var dayFormatter: DateFormatter {
        let df = DateFormatter()
        df.locale = Locale(identifier: english ? "en_GB" : "de_DE")
        df.timeZone = TimeZone(identifier: "Europe/Berlin")
        df.dateFormat = "yyyy-MM-dd"
        return df
    }
    private func formatted(_ value: String, _ pattern: String) -> String {
        guard let date = dayFormatter.date(from: value) else { return value }
        let f = dayFormatter
        f.dateFormat = pattern
        return f.string(from: date)
    }
    private func modeTitle(_ value: String) -> String {
        switch value {
        case "week": return tr("Woche", "Week")
        case "provider": return tr("Behandler", "Providers")
        case "service": return tr("Behandlung", "Services")
        default: return tr("Tag", "Day")
        }
    }
    private var providers: [[String: Any]] { items("providers") }
    private var services: [[String: Any]] { items("services") }
    private var columns: [[String: Any]] { items("columns") }
    private var events: [[String: Any]] { items("events") }
    private var bands: [[String: Any]] { items("bands") }
    private var cellWidth: CGFloat { mode == "week" ? 154 : (mode == "provider" || mode == "service" ? 196 : 0) }

    var body: some View {
        GeometryReader { geometry in
            let width = mode == "day" ? max(geometry.size.width - rulerWidth - 8, 270) : cellWidth
            VStack(spacing: 0) {
                header
                weekStrip
                filters
                HStack(spacing: 0) {
                    Image(systemName: "clock")
                        .font(.system(size: 12))
                        .foregroundColor(muted)
                        .frame(width: rulerWidth, height: 39)
                    ForEach(Array(columns.enumerated()), id: \.offset) { _, column in
                        Text(columnHeading(column))
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.primary)
                            .lineLimit(2)
                            .frame(width: width, height: 39)
                            .background(background)
                            .overlay(alignment: .trailing) { Rectangle().fill(stroke).frame(width: 0.5) }
                    }
                }
                .frame(width: rulerWidth + CGFloat(columns.count)*width, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(background)

                // Vertical scroll is independent of the horizontal week/provider
                // column scroll. SwiftUI preserves its position during date swipes.
                ScrollView(.horizontal, showsIndicators: mode != "day") {
                    ScrollViewReader { proxy in
                        ScrollView(.vertical, showsIndicators: true) {
                            HStack(alignment: .top, spacing: 0) {
                                ruler
                                ForEach(Array(columns.enumerated()), id: \.offset) { index, col in
                                    hourColumn(col: col, index: index, width: width)
                                }
                            }
                            .frame(height: hourHeight * 24, alignment: .top)
                            .frame(minWidth: rulerWidth + CGFloat(columns.count)*width, alignment: .leading)
                        }
                        .onAppear {
                            if !didInitialScroll {
                                didInitialScroll = true
                                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                                    proxy.scrollTo("hour-08", anchor: .top)
                                }
                            }
                        }
                        .simultaneousGesture(
                            DragGesture(minimumDistance: 60).onEnded { swipe in
                                if mode == "day" && abs(swipe.translation.width) > abs(swipe.translation.height) * 1.5 {
                                    move(swipe.translation.width < 0 ? "day-next" : "day-prev")
                                }
                            }
                        )
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.white)
                actionBar
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(.white)
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(tr("Kalender", "Calendar"))
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundColor(.primary)
                Text(formatted(selectedDate, "LLLL yyyy"))
                    .font(.system(size: 13))
                    .foregroundColor(muted)
            }
            Spacer(minLength: 8)
            Button(action: { move("cal-today") }) {
                Text(tr("Heute", "Today"))
                    .font(.system(size: 13, weight: .semibold))
                    .padding(.horizontal, 12)
                    .frame(height: 34)
                    .background(background)
                    .overlay(RoundedRectangle(cornerRadius: 9).stroke(stroke))
            }
            .accessibilityLabel(tr("Zum heutigen Datum", "Go to today"))
            Button(action: { move("week-prev") }) {
                Image(systemName: "chevron.left").frame(width: 32, height: 36)
            }
            .accessibilityLabel(tr("Vorherige Woche", "Previous week"))
            Button(action: { move("week-next") }) {
                Image(systemName: "chevron.right").frame(width: 32, height: 36)
            }
            .accessibilityLabel(tr("Nächste Woche", "Next week"))
        }
        .foregroundColor(accent)
        .padding(.horizontal, 15)
        .padding(.top, 7)
        .padding(.bottom, 5)
    }

    private var weekStrip: some View {
        HStack(spacing: 3) {
            ForEach(Array((model["week"] as? [String] ?? []).enumerated()), id: \.offset) { _, day in
                let selected = day == selectedDate
                Button(action: { move("date:" + day) }) {
                    VStack(spacing: 3) {
                        Text(formatted(day, "EEEEE"))
                            .font(.system(size: 11, weight: .medium))
                        Text(formatted(day, "dd"))
                            .font(.system(size: 15, weight: .semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 43)
                    .foregroundColor(selected ? .white : .primary)
                    .background(selected ? accent : background)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(formatted(day, "EEEE, d. MMMM yyyy"))
                .accessibilityAddTraits(selected ? [.isSelected] : [])
            }
        }
        .padding(.horizontal, 13)
        .padding(.bottom, 8)
        .simultaneousGesture(DragGesture(minimumDistance: 40).onEnded { value in
            if abs(value.translation.width) > abs(value.translation.height) * 1.5 {
                move(value.translation.width < 0 ? "week-next" : "week-prev")
            }
        })
    }

    private var filters: some View {
        HStack(spacing: 5) {
            Menu {
                ForEach(["day","week","provider","service"], id: \.self) { item in
                    Button(action: { move("cal-mode:" + item) }) {
                        Label(modeTitle(item), systemImage: mode == item ? "checkmark" : "calendar")
                    }
                }
            } label: {
                filterLabel(modeTitle(mode), symbol: "calendar")
            }
            Menu {
                Button(tr("Alle Behandler", "All providers")) { move("cal-provider:all") }
                ForEach(Array(providers.enumerated()), id: \.offset) { _, item in
                    Button(text(item, "label")) { move("cal-provider:" + text(item, "id")) }
                }
            } label: {
                filterLabel(selectedProvider == "all" ? tr("Behandler", "Provider") :
                    (providers.first { text($0,"id") == selectedProvider }.map { text($0, "label") } ?? tr("Behandler","Provider")),
                    symbol: "person.crop.rectangle")
            }
            Menu {
                Button(tr("Alle Behandlungen", "All services")) { move("cal-service:all") }
                ForEach(Array(services.enumerated()), id: \.offset) { _, item in
                    Button(text(item, "label")) { move("cal-service:" + text(item, "id")) }
                }
            } label: {
                filterLabel(selectedService == "all" ? tr("Behandlung", "Service") :
                    (services.first { text($0,"id") == selectedService }.map { text($0,"label") } ?? tr("Behandlung","Service")),
                    symbol: "line.3.horizontal.decrease")
            }
        }
        .padding(.horizontal, 12)
        .padding(.bottom, 7)
    }
    private func filterLabel(_ title: String, symbol: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: symbol).font(.system(size: 11))
            Text(title).font(.system(size: 11, weight: .medium)).lineLimit(1)
            Image(systemName: "chevron.down").font(.system(size: 9))
        }
        .foregroundColor(accent)
        .padding(.horizontal, 7)
        .frame(height: 32)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(stroke, lineWidth: 0.8))
    }

    private func columnHeading(_ col: [String: Any]) -> String {
        if mode == "week" { return formatted(text(col,"date"), "EEE, dd.MM.") }
        return mode == "day" ? formatted(selectedDate, "EEEE, d. MMMM") : text(col,"title")
    }

    private var ruler: some View {
        VStack(spacing: 0) {
            ForEach(0..<24, id: \.self) { hour in
                Text(String(format:"%02d:00", hour))
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(muted)
                    .frame(width: rulerWidth - 5, height: hourHeight, alignment: .topTrailing)
                    .padding(.trailing, 5)
                    .id("hour-\(String(format:"%02d", hour))")
            }
        }
        .frame(width: rulerWidth)
    }

    private func hourColumn(col: [String: Any], index: Int, width: CGFloat) -> some View {
        ZStack(alignment: .topLeading) {
            Color.white
            ForEach(0..<24, id: \.self) { hour in
                Rectangle()
                    .fill(stroke)
                    .frame(height: hour == 0 ? 1 : 0.6)
                    .offset(y: CGFloat(hour) * hourHeight)
            }
            ForEach(0..<48, id: \.self) { half in
                Rectangle()
                    .fill(stroke.opacity(0.38))
                    .frame(height: 0.5)
                    .offset(y: CGFloat(half) * hourHeight / 2)
            }
            ForEach(Array(bands.filter { value($0,"column") == index }.enumerated()), id: \.offset) { _, band in
                Rectangle()
                    .fill(Color(red: 0.91, green: 0.975, blue: 0.95))
                    .frame(height: CGFloat(value(band,"upper") - value(band,"lower")) * hourHeight / 60)
                    .offset(y: CGFloat(value(band,"lower")) * hourHeight / 60)
                    .allowsHitTesting(false)
            }
            ForEach(0..<48, id: \.self) { half in
                let clock = String(format:"%02d:%02d", half/2, (half%2)*30)
                Button(action: {
                    let staff = mode == "provider" ? text(col,"ref") : selectedProvider
                    move("slot:" + text(col,"date") + ":" + clock + ":" + staff)
                }) {
                    Color.clear
                }
                .frame(width: width, height: hourHeight / 2)
                .contentShape(Rectangle())
                .offset(y: CGFloat(half) * hourHeight / 2)
                .accessibilityLabel(tr("Freie Zeit", "Free time") + " " + clock)
                .buttonStyle(.plain)
            }
            ForEach(Array(events.filter { value($0,"column") == index }.enumerated()), id: \.offset) { _, event in
                eventCard(event, width: width)
            }
            Rectangle().fill(stroke).frame(width: 0.7)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .allowsHitTesting(false)
        }
        .frame(width: width, height: hourHeight * 24, alignment: .topLeading)
        .clipped()
    }

    private func eventCard(_ event: [String: Any], width: CGFloat) -> some View {
        let span = max(1, value(event,"upper") - value(event,"lower"))
        let lanes = max(1, value(event,"lanes"))
        let lane = value(event,"lane")
        let w = width / CGFloat(lanes)
        let height = max(25, CGFloat(span) * hourHeight / 60 - 1)
        let kind = text(event,"kind")
        let color: Color = kind == "appointment" ? Color(red:0.28, green:0.66, blue:0.85)
            : kind == "note" ? Color(red:0.98, green:0.90, blue:0.61)
            : Color(red:0.86, green:0.69, blue:0.33)
        let textColor: Color = kind == "appointment" ? .white : Color(red:0.20,green:0.23,blue:0.25)
        return Button(action: {
            let id = text(event, "id")
            if !id.isEmpty { move(id) }
        }) {
            VStack(alignment: .leading, spacing: 2) {
                Text((text(event, "start").isEmpty ? "" : text(event, "start")+" · ") + text(event, "title"))
                    .font(.system(size: 11, weight: .semibold))
                    .lineLimit(height < 46 ? 1 : 2)
                if height >= 44 {
                    Text(text(event,"detail"))
                        .font(.system(size: 10)).lineLimit(2)
                }
            }
            .foregroundColor(textColor)
            .padding(.horizontal, 5)
            .frame(maxWidth:.infinity, maxHeight:.infinity, alignment:.topLeading)
            .padding(.top, 4)
            .background(color)
            .clipShape(RoundedRectangle(cornerRadius:4))
        }
        .buttonStyle(.plain)
        .frame(width: max(20,w-2), height: height)
        .offset(x:CGFloat(lane)*w + 1,
                y:CGFloat(value(event,"lower")) * hourHeight / 60)
        .accessibilityLabel(text(event,"start")+" "+text(event,"title")+" "+text(event,"detail"))
    }

    private var actionBar: some View {
        HStack(spacing: 7) {
            Button(action:{move("new-appointment")}) {
                Label(tr("Termin", "Booking"),systemImage:"plus")
                    .frame(maxWidth:.infinity).frame(height:36)
            }
            .buttonStyle(.borderedProminent)
            .tint(accent)
            Button(action:{move("new-block")}) {
                Label(tr("Notiz / Sperrzeit", "Note / Block"),systemImage:"square.and.pencil")
                    .frame(maxWidth:.infinity).frame(height:36)
            }
            .buttonStyle(.bordered)
            .tint(accent)
            Button(action:{move("availability")}) {
                Image(systemName:"clock.badge.checkmark")
                    .frame(width:40,height:36)
            }
            .accessibilityLabel(tr("Arbeitszeiten", "Working hours"))
            .buttonStyle(.bordered)
            .tint(accent)
        }
        .font(.system(size:12,weight:.semibold))
        .padding(.horizontal,10)
        .padding(.vertical,6)
        .background(background)
    }
}

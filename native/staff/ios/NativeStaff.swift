// Native staff surface. Compiled into the generated Capacitor iOS target.
import SwiftUI
import PDFKit
import UniformTypeIdentifiers
import Capacitor
import UIKit

final class StaffScreenState: ObservableObject {
    @Published var screen: [String: Any] = [:]
    @Published var calendarScreen: [String: Any] = [:]
    @Published var values: [String: String] = [:]
    var send: ((String, [String: String]) -> Void)?
    func replace(_ next: [String: Any]) {
        values = [:]
        for field in (next["fields"] as? [[String: Any]] ?? []) {
            if let key = field["id"] as? String { values[key] = field["value"] as? String ?? "" }
        }
        screen = next
        if next["timeline"] != nil { calendarScreen = next }
        if next.isEmpty { calendarScreen = [:] }
    }
}

struct StaffNativeScreen: View {
    @ObservedObject var state: StaffScreenState
    @State private var privacyCover = false
    @State private var choosing: String? = nil
    @State private var choiceQuery = ""
    private let paper = Color(red: 247/255, green: 245/255, blue: 240/255)
    private let card = Color(red: 255/255, green: 252/255, blue: 248/255)
    private let ink = Color(red: 23/255, green: 41/255, blue: 35/255)
    private let green = Color(red: 19/255, green: 37/255, blue: 31/255)
    private let muted = Color(red: 104/255, green: 115/255, blue: 108/255)
    private let gold = Color(red: 204/255, green: 171/255, blue: 112/255)
    private let edge = Color(red: 230/255, green: 223/255, blue: 211/255)
    private let bronze = Color(red: 151/255, green: 111/255, blue: 58/255)
    private let sand = Color(red: 241/255, green: 229/255, blue: 204/255)
    private var modal: Bool { text(state.screen, "presentation") == "calendar-sheet" }
    private var simplyForm: Bool { text(state.screen,"layout") == "simplybook-form" }
    private let sbNavy = Color(red:32/255,green:43/255,blue:61/255)
    private let sbSection = Color(red:240/255,green:243/255,blue:252/255)
    private let sbLine = Color(red:220/255,green:226/255,blue:234/255)
    private var billing: Bool { text(state.screen, "theme") == "billing" }
    private var accent: Color { modal ? Color(red: 32/255,green: 43/255,blue: 61/255) : billing ? Color(red: 98/255,green: 12/255,blue: 14/255) : green }
    private var english: Bool { text(state.screen, "language") == "en" }
    private func t(_ de: String, _ en: String) -> String { english ? en : de }
    private func action(_ id: String) { state.send?(id, state.values) }
    private func items(_ key: String) -> [[String: Any]] { state.screen[key] as? [[String: Any]] ?? [] }
    private func text(_ item: [String: Any], _ key: String) -> String { item[key] as? String ?? "" }

    var body: some View {
        Group {
            if let calendar = state.screen["timeline"] as? [String: Any] {
                StaffSimplyBookV3(state: state, model: calendar)
            } else if simplyForm {
                simplyBookForm
            } else if modal, let calendar = state.calendarScreen["timeline"] as? [String: Any] {
                GeometryReader { geometry in
                    ZStack(alignment: .bottom) {
                        StaffSimplyBookV3(state: state, model: calendar).allowsHitTesting(false).accessibilityHidden(true)
                        Color.black.opacity(0.36).ignoresSafeArea().onTapGesture { action("calendar") }
                        surface(sheet: true)
                            .frame(maxWidth: 740).frame(height: geometry.size.height * 0.90)
                            .clipShape(RoundedRectangle(cornerRadius: 28))
                            .shadow(color: .black.opacity(0.24), radius: 24, y: -8)
                            .transition(.move(edge: .bottom))
                    }
                }
            } else {
                surface(sheet: modal)
            }
        }
            .overlay { choiceOverlay }
            .overlay { if privacyCover { paper.ignoresSafeArea() } }
            .onAppear { if simplyForm && !text(state.screen,"openChoice").isEmpty { choosing=text(state.screen,"openChoice"); choiceQuery=text(state.screen,"choiceQuery") } }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in privacyCover = true }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in privacyCover = false }
    }

    private func sbIcon(_ key: String) -> String {
        if key == "service_id" { return "sparkles" }
        if key == "staff_id" { return "person.crop.rectangle" }
        if key == "customer_id" { return "person" }
        if key == "date" { return "calendar" }
        if key.hasPrefix("start") || key.hasPrefix("end") { return "clock" }
        if key == "closed" { return "lock" }
        if key == "operation" { return "calendar.badge.clock" }
        return "note.text"
    }
    private var simplyBookForm: some View {
        let primary = items("actions").first(where: { text($0,"id").hasPrefix("save-") })
        let type = text(state.screen,"formType")
        let booking = type == "booking"
        let ready = !booking || text(primary ?? [:],"id") != "save-new" || ["service_id","staff_id","customer_id"].allSatisfy { !(state.values[$0] ?? "").isEmpty }
        return VStack(spacing:0) {
            HStack(spacing:12) {
                Button { action(modal ? "calendar" : "back") } label: { Image(systemName:"xmark").font(.system(size:18,weight:.medium)).frame(width:42,height:48) }.accessibilityLabel(t("Schließen","Close"))
                Text(text(state.screen,"title")).font(.system(size:19,weight:.medium)).lineLimit(2).minimumScaleFactor(0.78)
                Spacer(minLength:4)
                if let primary, !booking { Button { action(text(primary,"id")) } label: { Text(text(primary,"label")).font(.system(size:15,weight:.bold)).padding(.horizontal,13).frame(minHeight:48) } }
            }.foregroundColor(.white).padding(.horizontal,5).background(sbNavy)
            ScrollView {
                VStack(alignment:.leading,spacing:0) {
                    Text(booking ? t("Buchungsinformationen","Booking info") : type == "availability" ? t("Arbeitszeiten","Working hours") : t("Details","Details"))
                        .font(.system(size:17)).foregroundColor(sbNavy).padding(.horizontal,19).frame(maxWidth:.infinity,minHeight:54,alignment:.leading).background(sbSection)
                    if !text(state.screen,"message").isEmpty { Text(text(state.screen,"message")).font(.footnote).foregroundColor(sbNavy).padding(16).frame(maxWidth:.infinity,alignment:.leading).background(sbSection) }
                    sbFormFields(type)
                    ForEach(Array(items("rows").enumerated()),id:\.offset) { _, item in
                        Text(text(item,"label") + "  " + text(item,"detail")).font(.subheadline).padding(16).frame(maxWidth:.infinity,alignment:.leading)
                        Divider()
                    }
                    ForEach(Array(items("actions").filter { text($0,"id") != (primary.map { text($0,"id") } ?? "") }.enumerated()),id:\.offset) { _, item in
                        Button { action(text(item,"id")) } label: { Text(text(item,"label")).font(.system(size:15,weight:.semibold)).foregroundColor(text(item,"id").contains("remove") ? .red : Color(red:0,green:0.60,blue:0.78)).frame(maxWidth:.infinity,minHeight:53).background(sbSection) }.buttonStyle(.plain)
                    }
                }.background(Color.white)
            }.background(Color.white)
            if booking, let primary {
                Button { action(text(primary,"id")) } label: { Text(text(primary,"label")).font(.system(size:16,weight:.semibold)).foregroundColor(.white).frame(maxWidth:.infinity,minHeight:49).background(Color(red:0,green:0.60,blue:0.78).opacity(ready ? 1 : 0.42),in:Capsule()) }.disabled(!ready).buttonStyle(.plain).padding(.horizontal,20).padding(.vertical,12)
            }
        }.background(Color.white).preferredColorScheme(.light)
    }
    private func sbSectionTitle(_ label:String) -> some View { Text(label).font(.system(size:17)).foregroundColor(sbNavy).padding(.horizontal,19).frame(maxWidth:.infinity,minHeight:54,alignment:.leading).background(sbSection) }
    private func sbValue(_ key:String) -> Binding<String> { Binding(get:{state.values[key] ?? ""},set:{state.values[key]=$0}) }
    private func sbDatePair(_ time:String,_ label:String) -> some View {
        VStack(spacing:0) {
            HStack(spacing:15) {
                Image(systemName:"calendar").font(.system(size:19)).foregroundColor(sbNavy).frame(width:25)
                VStack(alignment:.leading,spacing:4) {
                    HStack(spacing:5) { TextField("TT.MM.JJJJ",text:sbValue("date")).frame(maxWidth:130); Text(","); TextField("HH:MM",text:sbValue(time)).frame(maxWidth:84) }.font(.system(size:16,weight:.bold)).foregroundColor(sbNavy).autocorrectionDisabled()
                    Text(label).font(.system(size:13)).foregroundColor(.gray)
                }; Spacer(minLength:0); Image(systemName:"pencil").foregroundColor(sbNavy)
            }.padding(.horizontal,19).padding(.vertical,13).frame(minHeight:68)
            Rectangle().fill(sbLine).frame(height:1)
        }
    }
    @ViewBuilder private func sbFormFields(_ type:String) -> some View {
        if type == "block" {
            sbDatePair("start",t("Startdatum und -uhrzeit","Start date and time"))
            sbDatePair("end",t("Enddatum und -uhrzeit","End date and time"))
            HStack(spacing:15) { Image(systemName:"lock").frame(width:25); VStack(alignment:.leading,spacing:4) { Text(state.values["kind"] == "block" ? t("Zeitraum ist geblockt","Time is blocked") : t("Zeitraum ist nicht geblockt","Time is not blocked")).font(.system(size:16,weight:.bold)); Text(t("Zeitraum ist geblockt","Time is blocked")).font(.caption).foregroundColor(.gray) }; Spacer(); Toggle("",isOn:Binding(get:{state.values["kind"] == "block"},set:{state.values["kind"]=$0 ? "block" : "note"})).labelsHidden().tint(Color(red:0,green:0.60,blue:0.78)) }.foregroundColor(sbNavy).padding(.horizontal,19).frame(minHeight:68)
            sbSectionTitle(t("Anwendung der Notiz","Apply note to"))
            HStack(spacing:0) { ForEach([t("Für alle anwenden","Apply to all"),t("Für Dienstleister anwenden","Apply to provider"),t("Für Dienstleistung anwenden","Apply to service")],id:\.self) { label in let selected = label == t("Für Dienstleister anwenden","Apply to provider"); Text(label).font(.system(size:12,weight:selected ? .bold : .regular)).foregroundColor(selected ? sbNavy : .gray).multilineTextAlignment(.center).frame(maxWidth:.infinity,minHeight:64).background(selected ? Color.white : sbSection.opacity(0.6)) } }
            ForEach(Array(items("fields").filter{["staff_id","text"].contains(text($0,"id"))}.enumerated()),id:\.offset) { _,field in sbField(field) }
            HStack(spacing:15) { Text("N").font(.system(size:16,weight:.bold)).foregroundColor(.white).frame(width:34,height:34).background(Color(red:0.95,green:0.77,blue:0.36),in:Circle()); VStack(alignment:.leading,spacing:4) { Text("Note").font(.system(size:16,weight:.bold)); Text(t("Art der Notiz","Note type")).font(.caption).foregroundColor(.gray) }; Spacer() }.foregroundColor(sbNavy).padding(.horizontal,19).frame(minHeight:68)
        } else if type == "booking" {
            ForEach(Array(items("fields").filter{["service_id","staff_id","customer_id"].contains(text($0,"id"))}.enumerated()),id:\.offset) { _, field in sbField(field) }
            sbDatePair("start",t("Datum und Uhrzeit der Buchung","Booking date and time"))
            HStack { Text(t("Einstellungen wiederkehrende Buchungen","Recurring booking settings")).font(.system(size:15)).foregroundColor(sbNavy); Spacer(); Toggle("",isOn:.constant(false)).labelsHidden().disabled(true) }.padding(.horizontal,19).frame(minHeight:66).background(sbSection).accessibilityHint(t("Nur in der Webverwaltung verfügbar","Available in web administration"))
            ForEach(Array(items("fields").filter{text($0,"id") == "notes"}.enumerated()),id:\.offset) { _,field in sbField(field) }
        } else { ForEach(Array(items("fields").enumerated()),id:\.offset) { _,field in sbField(field) } }
    }
    private func sbField(_ field:[String:Any]) -> some View {
        let key=text(field,"id"), kind=text(field,"kind"), label=text(field,"label")
        let binding=Binding(get:{state.values[key] ?? ""},set:{state.values[key]=$0})
        return VStack(spacing:0) {
            HStack(alignment:.center,spacing:15) {
                Image(systemName:sbIcon(key)).font(.system(size:19,weight:.regular)).foregroundColor(sbNavy).frame(width:25)
                if let options=field["options"] as? [[String:Any]] {
                    Button { choiceQuery=""; choosing=key } label: {
                        HStack {
                            VStack(alignment:.leading,spacing:4) {
                                if let selected=options.first(where:{text($0,"value")==binding.wrappedValue}) { Text(text(selected,"label")).font(.system(size:17,weight:.semibold)).foregroundColor(sbNavy); Text(label).font(.system(size:13)).foregroundColor(.gray) }
                                else { Text(key == "service_id" ? t("Eine Dienstleistung auswählen","Choose a service") : key == "customer_id" ? t("Einen Kunden auswählen","Choose a client") : t("Auswählen","Select")).font(.system(size:16)).foregroundColor(sbNavy) }
                            }; Spacer(); Image(systemName:"chevron.down").font(.system(size:15,weight:.medium)).foregroundColor(.gray)
                        }.frame(maxWidth:.infinity,alignment:.leading).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityLabel(label)
                } else {
                    VStack(alignment:.leading,spacing:4) {
                        if kind == "multiline" { TextEditor(text:binding).frame(minHeight:58).font(.system(size:16)).scrollContentBackground(.hidden).accessibilityLabel(label) }
                        else { TextField(label,text:binding).font(.system(size:17,weight:.semibold)).keyboardType(keyboardType(kind)).autocorrectionDisabled().accessibilityLabel(label) }
                        Text(label).font(.system(size:13)).foregroundColor(.gray)
                    }.foregroundColor(sbNavy)
                    Image(systemName:"pencil").font(.system(size:18)).foregroundColor(sbNavy)
                }
            }.padding(.horizontal,19).padding(.vertical,12).frame(minHeight:65).background(Color.white)
            Rectangle().fill(sbLine).frame(height:1)
        }
    }

    private func panel<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content().padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(modal ? Color.white : card, in: RoundedRectangle(cornerRadius: 17))
            .overlay { RoundedRectangle(cornerRadius: 17).strokeBorder(edge, lineWidth: 1) }
            .shadow(color:green.opacity(modal ? 0 : 0.055),radius:7,y:3)
    }
    private func sectionTitle(_ title: String) -> some View {
        Text(title).font(.system(size: 12, weight: .semibold)).tracking(1.1)
            .foregroundColor(modal ? muted : bronze).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 9)
    }
    private func icon(_ id: String) -> String {
        if id.hasPrefix("patient:") { return "person.crop.circle" }
        if id.hasPrefix("appointment:") { return "clock" }
        if id.hasPrefix("record:") { return "doc.text" }
        if id.contains("calendar") || id.contains("appointment") { return "calendar" }
        if id.contains("billing") || id.contains("invoice") { return "doc.plaintext" }
        if id.contains("intake") || id.contains("form") { return "checklist" }
        if id.contains("patient") { return "person.2" }
        return "arrow.up.right"
    }
    private func rowView(_ item: [String: Any]) -> some View {
        let id = text(item, "id")
        return Button { action(id) } label: {
            panel {
                HStack(alignment: .top, spacing: 13) {
                    if !id.isEmpty {
                        Image(systemName: icon(id)).font(.system(size: 18, weight: .medium))
                            .foregroundColor(modal ? accent : bronze).frame(width: 43, height: 43)
                            .background(modal ? accent.opacity(0.075) : sand, in: RoundedRectangle(cornerRadius: 12))
                    }
                    VStack(alignment: .leading, spacing: 5) {
                        Text(text(item, "label")).font(.system(size: 16, weight: .semibold)).foregroundColor(ink)
                        if !text(item, "detail").isEmpty {
                            Text(text(item, "detail")).font(.system(size: 13)).foregroundColor(muted).fixedSize(horizontal: false, vertical: true)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    if !text(item, "badge").isEmpty {
                        Text(text(item, "badge")).font(.caption2.weight(.semibold)).padding(6)
                            .background(modal ? accent.opacity(0.08) : sand, in: Capsule()).foregroundColor(modal ? accent : bronze)
                    }
                    if !id.isEmpty { Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundColor(muted).padding(.top, 4) }
                }
            }
        }.buttonStyle(.plain).disabled(id.isEmpty)
    }
    private func actionView(_ item: [String: Any], primary: Bool = false) -> some View {
        let id = text(item, "id")
        let destructive = id.contains("cancel-appointment") || id.contains("confirm-cancel") || id.contains("remove-block") || id.contains("delete-line")
        let tone: Color = destructive ? .red : accent
        return Button { action(id) } label: {
            HStack {
                if primary { Spacer(minLength: 0) }
                Text(text(item, "label")).font(.system(size: 15, weight: .semibold)).multilineTextAlignment(.leading)
                Spacer(minLength: 0)
                if !primary { Image(systemName: "arrow.right").font(.caption.weight(.semibold)).foregroundColor(modal ? tone : bronze) }
            }.padding(.horizontal, 15).frame(minHeight: 49)
                .foregroundColor(primary && !destructive ? .white : tone)
                .background(primary && !destructive ? tone : modal ? Color.white : sand.opacity(0.45), in: RoundedRectangle(cornerRadius: 13))
                .overlay { RoundedRectangle(cornerRadius: 13).strokeBorder(tone.opacity(0.22),lineWidth: 1) }
        }.buttonStyle(.plain)
    }
    private func surfaceHeader(sheet: Bool) -> some View {
        HStack(spacing: 10) {
                Button { action(sheet ? "calendar" : "back") } label: {
                    Image(systemName: sheet ? "xmark" : "chevron.left").font(.system(size: 17, weight: .semibold))
                        .frame(width: 46, height: 46).background(card, in: RoundedRectangle(cornerRadius: 13))
                }.accessibilityLabel(sheet ? t("Schließen","Close") : t("Zurück","Back"))
                Spacer()
                Text(sheet ? t("KALENDER","CALENDAR") : "A+ ESTHETIC").font(.system(size: 11,weight: .semibold)).tracking(2.2)
                Spacer()
                if !sheet {
                    Button { action("home") } label: { Image(systemName: "square.grid.2x2").frame(width: 46,height: 46).background(card,in:RoundedRectangle(cornerRadius: 13)) }.accessibilityLabel(t("Übersicht","Home"))
                } else { Color.clear.frame(width: 46,height: 46) }
        }.foregroundColor(accent).padding(.horizontal, 18).padding(.vertical, 8)
    }
    @ViewBuilder private func surfaceTitle(sheet: Bool) -> some View {
        if !text(state.screen,"hero").isEmpty {
            VStack(alignment:.leading,spacing:12) {
                Text("A+ ESTHETIC · " + (text(state.screen,"heroLabel").isEmpty ? t("PRAXISMANAGEMENT","PRACTICE MANAGEMENT") : text(state.screen,"heroLabel")))
                    .font(.system(size:10,weight:.semibold)).tracking(1.4).foregroundColor(gold)
                Text(text(state.screen,"hero")).font(.system(size:34,weight:.regular,design:.serif)).foregroundColor(.white)
                Text(text(state.screen,"subtitle")).font(.subheadline).foregroundColor(.white.opacity(0.78))
            }.padding(23).frame(maxWidth:.infinity,alignment:.leading)
                .background(LinearGradient(colors:[green,Color(red:0.19,green:0.29,blue:0.24)],startPoint:.topLeading,endPoint:.bottomTrailing))
                .overlay(alignment:.trailing) {
                    ZStack {
                        Circle().stroke(gold.opacity(0.14),lineWidth:28).frame(width:190,height:190)
                        Circle().stroke(gold.opacity(0.18),lineWidth:1).frame(width:140,height:140).offset(x:20,y:40)
                    }.offset(x:87,y:-45).allowsHitTesting(false).accessibilityHidden(true)
                }
                .clipShape(RoundedRectangle(cornerRadius:23))
                .shadow(color:green.opacity(0.18),radius:12,y:5)
        } else {
            Text(text(state.screen,"title")).font(.system(size:sheet ? 27 : 34,weight:.regular,design:sheet ? .default : .serif))
            if !text(state.screen,"subtitle").isEmpty { Text(text(state.screen,"subtitle")).font(.subheadline).foregroundColor(muted) }
        }
    }
    @ViewBuilder private var metricsView: some View {
        if !items("metrics").isEmpty {
            LazyVGrid(columns:[GridItem(.adaptive(minimum:140),spacing:10)],spacing:10) {
                ForEach(Array(items("metrics").enumerated()),id:\.offset) { _, item in
                    Button { action(text(item,"id")) } label: {
                        panel {
                            VStack(alignment:.leading,spacing:8) {
                                HStack { Image(systemName:icon(text(item,"id"))).font(.body.weight(.medium)).foregroundColor(bronze).frame(width:35,height:35).background(sand,in:RoundedRectangle(cornerRadius:10)); Spacer(); Image(systemName:"chevron.right").font(.caption2.weight(.semibold)).foregroundColor(bronze) }
                                Text(text(item,"label").uppercased()).font(.system(size:10,weight:.semibold)).tracking(0.5).foregroundColor(bronze).lineLimit(2)
                                Text(text(item,"detail")).font(.system(size:31,weight:.semibold,design:.serif)).foregroundColor(ink).minimumScaleFactor(0.6).lineLimit(1)
                            }
                        }
                    }.buttonStyle(.plain).disabled(text(item,"id").isEmpty)
                }
            }
        }
    }
    @ViewBuilder private var segmentsView: some View {
        if !items("segments").isEmpty {
            ScrollView(.horizontal,showsIndicators:false) {
                HStack(spacing:7) {
                    ForEach(Array(items("segments").enumerated()),id:\.offset) { _, item in
                        let selected = item["selected"] as? Bool == true
                        Button { action(text(item,"id")) } label: {
                            Text(text(item,"label")).font(.subheadline.weight(.semibold)).padding(.horizontal,13).padding(.vertical,11)
                                .foregroundColor(selected ? green : accent).background(selected ? sand : card,in:Capsule())
                                .overlay { Capsule().strokeBorder(selected ? gold : edge,lineWidth:1) }
                        }.buttonStyle(.plain)
                    }
                }
            }
        }
    }
    @ViewBuilder private var formView: some View {
        if !text(state.screen,"message").isEmpty {
            panel { HStack(alignment:.top,spacing:10) {
                Image(systemName:"info.circle").foregroundColor(accent)
                Text(text(state.screen,"message")).font(.subheadline).foregroundColor(ink)
            } }
        }
        if !items("fields").isEmpty {
            panel { VStack(alignment:.leading,spacing:17) {
                ForEach(Array(items("fields").enumerated()),id:\.offset) { _, field in fieldView(field) }
            } }
        }
    }
    @ViewBuilder private var shortcutsView: some View {
        if !items("shortcuts").isEmpty {
            sectionTitle(t("SCHNELLZUGRIFF","QUICK ACCESS"))
            LazyVGrid(columns:[GridItem(.adaptive(minimum:140),spacing:9)],spacing:9) {
                ForEach(Array(items("shortcuts").enumerated()),id:\.offset) { _, item in
                    Button { action(text(item,"id")) } label: {
                        HStack(spacing:8) {
                            Image(systemName:icon(text(item,"id"))).font(.system(size:13,weight:.semibold)).foregroundColor(bronze).frame(width:30,height:30).background(sand,in:RoundedRectangle(cornerRadius:9))
                            Text(text(item,"label")).font(.system(size:13,weight:.semibold)).foregroundColor(ink).multilineTextAlignment(.leading)
                            Spacer(minLength:0); Image(systemName:"chevron.right").font(.caption2.weight(.semibold)).foregroundColor(bronze)
                        }.padding(10).frame(minHeight:60).frame(maxWidth:.infinity,alignment:.leading)
                            .background(sand.opacity(0.33),in:RoundedRectangle(cornerRadius:13)).overlay { RoundedRectangle(cornerRadius:13).strokeBorder(edge,lineWidth:1) }
                    }.buttonStyle(.plain)
                }
            }
        }
    }
    @ViewBuilder private var recordsView: some View {
        if !text(state.screen,"sectionTitle").isEmpty { sectionTitle(text(state.screen,"sectionTitle")) }
        ForEach(Array(items("rows").enumerated()),id:\.offset) { _, item in rowView(item) }
        if items("rows").isEmpty && !text(state.screen,"empty").isEmpty {
            panel { VStack(alignment:.center,spacing:10) {
                Image(systemName:"tray").font(.system(size:29)).foregroundColor(muted)
                Text(text(state.screen,"empty")).font(.subheadline).foregroundColor(muted).multilineTextAlignment(.center)
            }.frame(maxWidth:.infinity).padding(.vertical,12) }
        }
        if !items("secondaryRows").isEmpty {
            sectionTitle(text(state.screen,"secondaryTitle"))
            ForEach(Array(items("secondaryRows").enumerated()),id:\.offset) { _, item in rowView(item) }
        }
        if let data=Data(base64Encoded:text(state.screen,"image")),let image=UIImage(data:data) {
            panel { Image(uiImage:image).resizable().scaledToFit().frame(maxHeight:480).accessibilityLabel(t("Dokument","Document")) }
        }
    }
    private var navigationView: some View {
        HStack(spacing:3) {
                    ForEach(Array(items("tabs").enumerated()),id:\.offset) { _, tab in
                        let selected = tab["selected"] as? Bool == true
                        Button { action(text(tab,"id")) } label: {
                            VStack(spacing:5) {
                                Image(systemName:text(tab,"icon")).font(.system(size:19,weight:selected ? .semibold:.regular))
                                Text(text(tab,"label")).font(.system(size:10,weight:selected ? .semibold:.regular)).lineLimit(1).minimumScaleFactor(0.72)
                            }.frame(maxWidth:.infinity).frame(minHeight:58)
                                .foregroundColor(selected ? .white : muted)
                                .background(selected ? accent : Color.clear,in:RoundedRectangle(cornerRadius:13))
                        }.buttonStyle(.plain).accessibilityAddTraits(selected ? .isSelected : [])
                    }
        }.padding(8).background(card)
    }
    private func surface(sheet: Bool) -> some View {
        VStack(spacing:0) {
            if sheet { Capsule().fill(muted.opacity(0.35)).frame(width:38,height:4).padding(.top,9) }
            surfaceHeader(sheet:sheet)
            ScrollView {
                VStack(alignment:.leading,spacing:11) {
                    surfaceTitle(sheet:sheet)
                    if state.screen["busy"] as? Bool == true {
                        VStack(spacing:10) { ForEach(0..<3) { _ in RoundedRectangle(cornerRadius:13).fill(edge.opacity(0.7)).frame(height:70) } }
                            .accessibilityLabel(t("Wird geladen","Loading"))
                    }
                    metricsView
                    segmentsView
                    formView
                    shortcutsView
                    recordsView
                    ForEach(Array(items("actions").enumerated()),id:\.offset) { index,item in actionView(item,primary:index == 0) }
                }.padding(18).frame(maxWidth:850).frame(maxWidth:.infinity)
            }
            if !sheet { navigationView }
        }.foregroundColor(ink).background(paper.ignoresSafeArea()).preferredColorScheme(.light)
    }

    @ViewBuilder private var choiceOverlay: some View {
        if let key = choosing, let field = items("fields").first(where: { text($0,"id") == key }),
           let options = field["options"] as? [[String: Any]] {
            if simplyForm {
                sbSelector(key,field,options)
            } else { ZStack(alignment:.bottom) {
                Color.black.opacity(0.35).ignoresSafeArea().onTapGesture { choosing=nil }
                VStack(alignment:.leading,spacing:10) {
                    HStack { Text(text(field,"label")).font(.title2.weight(.semibold)); Spacer(); Button { choosing=nil } label: { Image(systemName:"xmark.circle.fill").font(.title2).foregroundColor(muted) } }
                    ScrollView {
                        VStack(spacing: 5) {
                            ForEach(Array(options.enumerated()),id:\.offset) { _, option in
                                Button { state.values[key]=text(option,"value"); choosing=nil } label: {
                                    HStack {
                                        Text(text(option,"label")).font(.body).foregroundColor(ink).multilineTextAlignment(.leading)
                                        Spacer()
                                        if state.values[key] == text(option,"value") { Image(systemName:"checkmark.circle.fill").foregroundColor(accent) }
                                    }.padding(14).frame(maxWidth:.infinity,alignment:.leading)
                                        .background(card,in:RoundedRectangle(cornerRadius:10))
                                }.buttonStyle(.plain)
                            }
                        }
                    }.frame(maxHeight:430)
                }.padding(20).frame(maxWidth:680).background(paper,in:RoundedRectangle(cornerRadius:24)).padding(.bottom,8)
            } }
        }
    }

    private func sbSelector(_ key:String,_ field:[String:Any],_ options:[[String:Any]]) -> some View {
        let client = key == "customer_id"
        let shown = choiceQuery.isEmpty || client ? options : options.filter{text($0,"label").localizedCaseInsensitiveContains(choiceQuery)}
        return GeometryReader { geometry in
            ZStack {
                Color.black.opacity(0.45).ignoresSafeArea().onTapGesture { choosing=nil }
                VStack(alignment:.leading,spacing:13) {
                    Text(client ? t("Kunde wählen","Choose client") : text(field,"label")).font(.system(size:17,weight:.bold)).foregroundColor(sbNavy)
                    HStack { TextField(t("Suchen...","Search..."),text:$choiceQuery).submitLabel(.search).onSubmit { if client { state.send?("calendar-client-search",state.values.merging(["_patient_query":choiceQuery]){$1}) } }; Button { if client { state.send?("calendar-client-search",state.values.merging(["_patient_query":choiceQuery]){$1}) } } label:{Image(systemName:"magnifyingglass").foregroundColor(sbNavy)} }.padding(10).background(sbSection,in:RoundedRectangle(cornerRadius:5))
                    if client { Text(t("Neuen Kunden hinzufügen · Web","Add new client · Web")).font(.subheadline.weight(.semibold)).foregroundColor(Color(red:0,green:0.60,blue:0.78)).frame(maxWidth:.infinity).padding(.top,18).accessibilityHint(t("In der Webverwaltung verfügbar","Available in web administration")) }
                    ScrollView {
                        VStack(spacing:0) { ForEach(Array(shown.enumerated()),id:\.offset) { _, option in
                            Button { state.values[key]=text(option,"value"); choosing=nil } label: {
                                HStack(spacing:11) {
                                    if client { Text(String(text(option,"label").prefix(1)).uppercased()).font(.system(size:15,weight:.medium)).foregroundColor(.white).frame(width:36,height:36).background(sbNavy,in:Circle()) }
                                    VStack(alignment:.leading,spacing:4) { Text(text(option,"label")).font(.system(size:15)).foregroundColor(sbNavy); if !text(option,"detail").isEmpty { Text(text(option,"detail")).font(.system(size:11)).foregroundColor(.gray) } }; Spacer(); if state.values[key]==text(option,"value") { Image(systemName:"checkmark").foregroundColor(sbNavy) }
                                }.frame(maxWidth:.infinity,minHeight:49,alignment:.leading).contentShape(Rectangle())
                            }.buttonStyle(.plain)
                        } }
                    }.frame(maxHeight:.infinity)
                    HStack { Spacer(); Button(t("Abbrechen","Cancel")) { choosing=nil }.font(.system(size:15,weight:.bold)).foregroundColor(sbNavy) }
                }.padding(17).frame(width:min(geometry.size.width-44,390),height:min(geometry.size.height-60,640)).background(Color.white,in:RoundedRectangle(cornerRadius:12)).shadow(color:.black.opacity(0.24),radius:10)
            }.frame(maxWidth:.infinity,maxHeight:.infinity)
        }
    }

    private func keyboardType(_ kind: String) -> UIKeyboardType {
        switch kind {
        case "integer": return .numberPad
        case "decimal": return .decimalPad
        case "email": return .emailAddress
        case "phone": return .phonePad
        default: return .default
        }
    }

    @ViewBuilder private func fieldView(_ field: [String: Any]) -> some View {
        let key = text(field, "id")
        let kind = text(field, "kind")
        let binding = Binding(get: { state.values[key] ?? "" }, set: { state.values[key] = $0 })
        VStack(alignment: .leading, spacing: 7) {
            Text(text(field, "label")).font(.system(size:13,weight:.semibold)).foregroundColor(muted)
            if let options = field["options"] as? [[String: Any]], !options.isEmpty {
                if kind == "choice-grid" {
                    LazyVGrid(columns:[GridItem(.flexible(),spacing:7),GridItem(.flexible(),spacing:7)],spacing:7) {
                        ForEach(Array(options.enumerated()),id:\.offset) { _, option in
                            let selected = binding.wrappedValue == text(option,"value")
                            Button { binding.wrappedValue=text(option,"value") } label: {
                                Text(text(option,"label")).font(.subheadline.weight(.semibold))
                                    .frame(maxWidth:.infinity).frame(minHeight:48)
                                    .foregroundColor(selected ? .white : accent)
                                    .background(selected ? accent : card,in:RoundedRectangle(cornerRadius:10))
                                    .overlay { RoundedRectangle(cornerRadius:10).strokeBorder(accent.opacity(0.3),lineWidth:1) }
                            }.buttonStyle(.plain).accessibilityAddTraits(selected ? .isSelected : [])
                        }
                    }
                } else {
                    Button { choosing=key } label: {
                        HStack {
                            Text(options.first(where:{ text($0,"value")==binding.wrappedValue }).map{ text($0,"label") } ?? t("Auswählen","Select"))
                                .foregroundColor(ink).multilineTextAlignment(.leading)
                            Spacer(); Image(systemName:"chevron.up.chevron.down").font(.caption).foregroundColor(accent)
                        }.padding(12).frame(minHeight:47).frame(maxWidth:.infinity,alignment:.leading)
                    }.buttonStyle(.plain)
                }
            } else if kind == "multiline" {
                TextEditor(text: binding)
                    .font(.body).frame(minHeight: 100).padding(8)
                    .accessibilityLabel(text(field, "label"))
            } else {
                TextField(text(field, "label"), text: binding)
                    .keyboardType(keyboardType(kind))
                    .textInputAutocapitalization(kind == "email" ? .never : .sentences)
                    .autocorrectionDisabled(["integer", "decimal", "email", "phone"].contains(kind))
                    .padding(12).frame(minHeight:47)
            }
        }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(paper.opacity(0.7),in:RoundedRectangle(cornerRadius:12))
            .overlay { RoundedRectangle(cornerRadius:12).strokeBorder(edge,lineWidth:1) }
    }
}

@objc(NativeStaffPlugin)
public final class NativeStaffPlugin: CAPPlugin, CAPBridgedPlugin, UIDocumentPickerDelegate, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
    public let identifier = "NativeStaffPlugin"
    public let jsName = "NativeStaff"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "present", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "render", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "dismiss", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "previewPDF", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "pickPDF", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "pickPhoto", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "takePhoto", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "probe", returnType: CAPPluginReturnPromise)
    ]
    // Non-sensitive native bridge health check. No patient data or credentials.
    @objc func probe(_ call: CAPPluginCall) {
        call.resolve(["ok": true, "native": true, "bridge": "NativeStaff"])
    }
    private var pickCall: CAPPluginCall?
    private var photoCall: CAPPluginCall?
    private var state: StaffScreenState?
    private var host: UIHostingController<StaffNativeScreen>?

    @objc func present(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard let screen = call.getObject("screen"), self.host == nil,
                  let presenter = self.bridge?.viewController else {
                call.reject("Native screen unavailable"); return
            }
            let state = StaffScreenState()
            state.send = { [weak self] id, values in self?.notifyListeners("action", data: ["id": id, "values": values]) }
            state.replace(screen)
            let host = UIHostingController(rootView: StaffNativeScreen(state: state))
            host.modalPresentationStyle = .fullScreen
            host.isModalInPresentation = true
            self.state = state
            self.host = host
            presenter.present(host, animated: true) { call.resolve() }
        }
    }
    @objc func render(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard let screen = call.getObject("screen"), let state = self.state else {
                call.reject("Native screen not active"); return
            }
            state.replace(screen); call.resolve()
        }
    }
    @objc func pickPDF(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard self.pickCall == nil, let host = self.host else {
                call.reject("Picker unavailable"); return
            }
            let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.pdf], asCopy: true)
            picker.delegate = self
            picker.allowsMultipleSelection = false
            self.pickCall = call
            host.present(picker, animated: true)
        }
    }
    @objc func pickPhoto(_ call: CAPPluginCall) { openPhoto(call,source:.photoLibrary) }
    @objc func takePhoto(_ call: CAPPluginCall) { openPhoto(call,source:.camera) }
    private func openPhoto(_ call: CAPPluginCall,source:UIImagePickerController.SourceType) {
        DispatchQueue.main.async {
            guard self.pickCall == nil, self.photoCall == nil, let host=self.host,
                  UIImagePickerController.isSourceTypeAvailable(source) else { call.reject("Photo source unavailable");return }
            let picker=UIImagePickerController()
            picker.sourceType=source
            picker.mediaTypes=[UTType.image.identifier]
            picker.delegate=self
            picker.allowsEditing=false
            picker.modalPresentationStyle = .fullScreen
            self.photoCall=call
            host.present(picker,animated:true)
        }
    }
    public func imagePickerControllerDidCancel(_ picker:UIImagePickerController) {
        picker.dismiss(animated:true)
        photoCall?.resolve(["cancelled":true]);photoCall=nil
    }
    public func imagePickerController(_ picker:UIImagePickerController,didFinishPickingMediaWithInfo info:[UIImagePickerController.InfoKey:Any]) {
        guard let call=photoCall else { picker.dismiss(animated:true);return }
        photoCall=nil
        picker.dismiss(animated:true)
        guard let image=info[.originalImage] as? UIImage else { call.reject("Image unavailable");return }
        let ratio=min(1,2400/max(image.size.width,image.size.height))
        let format=UIGraphicsImageRendererFormat();format.scale=1;format.opaque=true
        let size=CGSize(width:max(1,image.size.width*ratio),height:max(1,image.size.height*ratio))
        let normalized=UIGraphicsImageRenderer(size:size,format:format).image { _ in image.draw(in:CGRect(origin:.zero,size:size)) }
        guard let data=normalized.jpegData(compressionQuality:0.85),data.count<=6*1024*1024 else { call.reject("Image exceeds 6 MB");return }
        call.resolve(["filename":"patient-photo.jpg","base64":data.base64EncodedString()])
    }
    public func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        pickCall?.resolve(["cancelled": true]); pickCall = nil
    }
    public func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let call = pickCall else { return }
        pickCall = nil
        guard let url = urls.first else { call.resolve(["cancelled": true]); return }
        DispatchQueue.global(qos: .userInitiated).async {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            do {
                let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
                guard size > 0, size <= 6 * 1024 * 1024 else { call.reject("File exceeds 6 MB"); return }
                let data = try Data(contentsOf: url)
                guard data.count <= 6 * 1024 * 1024, data.starts(with: Data("%PDF-".utf8)) else {
                    call.reject("Invalid PDF"); return
                }
                call.resolve(["filename": url.lastPathComponent, "base64": data.base64EncodedString()])
            } catch { call.reject("Unable to read PDF") }
        }
    }
    @objc func previewPDF(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard let encoded = call.getString("base64"), encoded.count <= 11000000,
                  let data = Data(base64Encoded: encoded), let document = PDFDocument(data: data),
                  let presenter = self.host else {
                call.reject("PDF unavailable"); return
            }
            let pdf = PDFView()
            pdf.document = document
            pdf.autoScales = true
            let content = UIViewController()
            content.view = pdf
            content.navigationItem.title = call.getString("title") ?? "PDF"
            content.navigationItem.leftBarButtonItem = UIBarButtonItem(
                systemItem: .done, primaryAction: UIAction { [weak content] _ in content?.dismiss(animated: true) })
            let nav = UINavigationController(rootViewController: content)
            nav.modalPresentationStyle = .fullScreen
            presenter.present(nav, animated: true) { call.resolve() }
        }
    }
    @objc func dismiss(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.state?.replace([:])
            self.host?.dismiss(animated: true)
            self.host = nil; self.state = nil
            call.resolve()
        }
    }
}

class StaffBridgeViewController: CAPBridgeViewController {
#if DEBUG && targetEnvironment(simulator)
    private var syntheticQAHost: UIHostingController<StaffNativeScreen>?
#endif
    override open func capacitorDidLoad() {
        super.capacitorDidLoad()
        bridge?.registerPluginInstance(NativeStaffPlugin())
        NSLog("APLUS_NATIVE_STAFF_REGISTERED bridge=%@", bridge == nil ? "missing" : "available")
    }
#if DEBUG
    override open func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
#if targetEnvironment(simulator)
        // Simulator-only visual fixture, never reads credentials or connects
        // this view to a real patient's API. Normal app launch is unchanged.
        if syntheticQAHost == nil,
           let payload = ProcessInfo.processInfo.environment["APLUS_NATIVE_QA_FIXTURE"],
           payload.count < 160000,
           let data = Data(base64Encoded:payload),
           let fixture = (try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
           let screen = fixture["screen"] as? [String:Any] {
            let state=StaffScreenState()
            state.calendarScreen=fixture["calendar"] as? [String:Any] ?? [:]
            state.replace(screen)
            let host=UIHostingController(rootView:StaffNativeScreen(state:state))
            host.modalPresentationStyle = .fullScreen
            syntheticQAHost=host
            present(host,animated:false)
            return
        }
#endif
        // Probe the real Capacitor JS-to-Swift bridge in iOS Simulator before
        // signing in. No tokens, account identifiers or patient data involved.
        DispatchQueue.main.asyncAfter(deadline: .now() + 7) { [weak self] in
            self?.webView?.evaluateJavaScript(
                "window.APlusNativeStaffProbeResult && window.APlusNativeStaffProbeResult.code || 'PROBE_PENDING'"
            ) { value, error in
                if let error = error {
                    NSLog("APLUS_NATIVE_STAFF_JS_BRIDGE ERROR")
                } else if let code = value as? String {
                    NSLog("APLUS_NATIVE_STAFF_JS_BRIDGE %@", code)
                } else {
                    NSLog("APLUS_NATIVE_STAFF_JS_BRIDGE UNKNOWN")
                }
            }
        }
    }
#endif
}

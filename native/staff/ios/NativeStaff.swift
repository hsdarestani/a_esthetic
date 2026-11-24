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
    private let paper = Color(red: 247/255, green: 245/255, blue: 240/255)
    private let card = Color(red: 255/255, green: 252/255, blue: 248/255)
    private let ink = Color(red: 23/255, green: 41/255, blue: 35/255)
    private let green = Color(red: 19/255, green: 37/255, blue: 31/255)
    private let muted = Color(red: 104/255, green: 115/255, blue: 108/255)
    private let gold = Color(red: 204/255, green: 171/255, blue: 112/255)
    private let edge = Color(red: 230/255, green: 223/255, blue: 211/255)
    private var modal: Bool { text(state.screen, "presentation") == "calendar-sheet" }
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
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in privacyCover = true }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in privacyCover = false }
    }

    private func panel<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content().padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(card, in: RoundedRectangle(cornerRadius: 17))
            .overlay { RoundedRectangle(cornerRadius: 17).strokeBorder(edge, lineWidth: 1) }
    }
    private func sectionTitle(_ title: String) -> some View {
        Text(title).font(.system(size: 12, weight: .semibold)).tracking(1.1)
            .foregroundColor(muted).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 9)
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
                            .foregroundColor(accent).frame(width: 43, height: 43)
                            .background(accent.opacity(0.075), in: RoundedRectangle(cornerRadius: 12))
                    }
                    VStack(alignment: .leading, spacing: 5) {
                        Text(text(item, "label")).font(.system(size: 16, weight: .semibold)).foregroundColor(ink)
                        if !text(item, "detail").isEmpty {
                            Text(text(item, "detail")).font(.system(size: 13)).foregroundColor(muted).fixedSize(horizontal: false, vertical: true)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    if !text(item, "badge").isEmpty {
                        Text(text(item, "badge")).font(.caption2.weight(.semibold)).padding(6)
                            .background(accent.opacity(0.08), in: Capsule()).foregroundColor(accent)
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
                if !primary { Image(systemName: "arrow.right").font(.caption.weight(.semibold)) }
            }.padding(.horizontal, 15).frame(minHeight: 49)
                .foregroundColor(primary && !destructive ? .white : tone)
                .background(primary && !destructive ? tone : card, in: RoundedRectangle(cornerRadius: 13))
                .overlay { RoundedRectangle(cornerRadius: 13).strokeBorder(tone.opacity(0.22),lineWidth: 1) }
        }.buttonStyle(.plain)
    }
    @ViewBuilder private func surface(sheet: Bool) -> some View {
        VStack(spacing: 0) {
            if sheet {
                Capsule().fill(muted.opacity(0.35)).frame(width: 38,height: 4).padding(.top, 9)
            }
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
            ScrollView {
                VStack(alignment: .leading, spacing: 11) {
                    if !text(state.screen, "hero").isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("A+ ESTHETIC · " + t("PRAXISMANAGEMENT","PRACTICE MANAGEMENT"))
                                .font(.system(size: 10,weight: .semibold)).tracking(1.4).foregroundColor(gold)
                            Text(text(state.screen,"hero")).font(.system(size: 34,weight: .regular,design: .serif)).foregroundColor(.white)
                            Text(text(state.screen,"subtitle")).font(.subheadline).foregroundColor(.white.opacity(0.78))
                        }.padding(23).frame(maxWidth: .infinity,alignment: .leading)
                            .background(LinearGradient(colors:[green,Color(red:0.19,green:0.29,blue:0.24)],startPoint:.topLeading,endPoint:.bottomTrailing),in:RoundedRectangle(cornerRadius: 23))
                    } else {
                        Text(text(state.screen,"title")).font(.system(size: sheet ? 27 : 34,weight: .regular,design: sheet ? .default : .serif))
                        if !text(state.screen,"subtitle").isEmpty { Text(text(state.screen,"subtitle")).font(.subheadline).foregroundColor(muted) }
                    }
                    if state.screen["busy"] as? Bool == true {
                        VStack(spacing: 10) { ForEach(0..<3) { _ in RoundedRectangle(cornerRadius: 13).fill(edge.opacity(0.7)).frame(height: 70) } }
                            .accessibilityLabel(t("Wird geladen","Loading"))
                    }
                    if !items("metrics").isEmpty {
                        LazyVGrid(columns:[GridItem(.adaptive(minimum: 140),spacing: 10)],spacing: 10) {
                            ForEach(Array(items("metrics").enumerated()),id:\.offset) { _, item in
                                Button { action(text(item,"id")) } label: {
                                    panel {
                                        VStack(alignment:.leading,spacing: 8) {
                                            Image(systemName: icon(text(item,"id"))).font(.body.weight(.medium)).foregroundColor(accent)
                                            Text(text(item,"detail")).font(.system(size: 29,weight: .semibold,design: .rounded)).foregroundColor(ink)
                                            Text(text(item,"label")).font(.caption.weight(.medium)).foregroundColor(muted)
                                        }
                                    }
                                }.buttonStyle(.plain).disabled(text(item,"id").isEmpty)
                            }
                        }
                    }
                    if !items("segments").isEmpty {
                        ScrollView(.horizontal,showsIndicators:false) {
                            HStack(spacing:7) {
                                ForEach(Array(items("segments").enumerated()),id:\.offset) { _, item in
                                    Button { action(text(item,"id")) } label: {
                                        Text(text(item,"label")).font(.subheadline.weight(.semibold)).padding(.horizontal,13).padding(.vertical,11)
                                            .foregroundColor(item["selected"] as? Bool == true ? .white : accent)
                                            .background(item["selected"] as? Bool == true ? accent : card,in:Capsule())
                                    }.buttonStyle(.plain)
                                }
                            }
                        }
                    }
                    if !text(state.screen,"message").isEmpty {
                        panel { HStack(alignment:.top,spacing:10) {
                            Image(systemName:"info.circle").foregroundColor(accent)
                            Text(text(state.screen,"message")).font(.subheadline).foregroundColor(ink)
                        } }
                    }
                    if !items("fields").isEmpty {
                        panel { VStack(alignment:.leading,spacing: 17) {
                            ForEach(Array(items("fields").enumerated()),id:\.offset) { _, field in fieldView(field) }
                        } }
                    }
                    if !items("shortcuts").isEmpty {
                        sectionTitle(t("SCHNELLZUGRIFF","QUICK ACCESS"))
                        LazyVGrid(columns:[GridItem(.adaptive(minimum: 140),spacing: 9)],spacing:9) {
                            ForEach(Array(items("shortcuts").enumerated()),id:\.offset) { _, item in
                                actionView(item)
                            }
                        }
                    }
                    if !text(state.screen,"sectionTitle").isEmpty { sectionTitle(text(state.screen,"sectionTitle")) }
                    ForEach(Array(items("rows").enumerated()),id:\.offset) { _, item in rowView(item) }
                    if items("rows").isEmpty && !text(state.screen,"empty").isEmpty {
                        panel { VStack(alignment:.center,spacing: 10) {
                            Image(systemName:"tray").font(.system(size: 29)).foregroundColor(muted)
                            Text(text(state.screen,"empty")).font(.subheadline).foregroundColor(muted).multilineTextAlignment(.center)
                        }.frame(maxWidth:.infinity).padding(.vertical,12) }
                    }
                    if !items("secondaryRows").isEmpty {
                        sectionTitle(text(state.screen,"secondaryTitle"))
                        ForEach(Array(items("secondaryRows").enumerated()),id:\.offset) { _, item in rowView(item) }
                    }
                    if let data = Data(base64Encoded: text(state.screen,"image")), let image = UIImage(data: data) {
                        panel { Image(uiImage:image).resizable().scaledToFit().frame(maxHeight:480).accessibilityLabel(t("Dokument","Document")) }
                    }
                    ForEach(Array(items("actions").enumerated()),id:\.offset) { index,item in actionView(item,primary:index == 0) }
                }.padding(18).frame(maxWidth: 850).frame(maxWidth: .infinity)
            }.scrollDismissesKeyboard(.interactively)
            if !sheet {
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
        }.foregroundColor(ink).background(paper.ignoresSafeArea()).preferredColorScheme(.light)
    }

    @ViewBuilder private var choiceOverlay: some View {
        if let key = choosing, let field = items("fields").first(where: { text($0,"id") == key }),
           let options = field["options"] as? [[String: Any]] {
            ZStack(alignment:.bottom) {
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
            }
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
                Button { choosing=key } label: {
                    HStack {
                        Text(options.first(where:{ text($0,"value")==binding.wrappedValue }).map{ text($0,"label") } ?? t("Auswählen","Select"))
                            .foregroundColor(ink).multilineTextAlignment(.leading)
                        Spacer(); Image(systemName:"chevron.up.chevron.down").font(.caption).foregroundColor(accent)
                    }.padding(12).frame(minHeight:47).frame(maxWidth:.infinity,alignment:.leading)
                }.buttonStyle(.plain)
            } else if kind == "multiline" {
                TextEditor(text: binding)
                    .font(.body).frame(minHeight: 100).scrollContentBackground(.hidden).padding(8)
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
public final class NativeStaffPlugin: CAPPlugin, CAPBridgedPlugin, UIDocumentPickerDelegate {
    public let identifier = "NativeStaffPlugin"
    public let jsName = "NativeStaff"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "present", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "render", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "dismiss", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "previewPDF", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "pickPDF", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "probe", returnType: CAPPluginReturnPromise)
    ]
    // Non-sensitive native bridge health check. No patient data or credentials.
    @objc func probe(_ call: CAPPluginCall) {
        call.resolve(["ok": true, "native": true, "bridge": "NativeStaff"])
    }
    private var pickCall: CAPPluginCall?
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
    override open func capacitorDidLoad() {
        super.capacitorDidLoad()
        bridge?.registerPluginInstance(NativeStaffPlugin())
        NSLog("APLUS_NATIVE_STAFF_REGISTERED bridge=%@", bridge == nil ? "missing" : "available")
    }
#if DEBUG
    override open func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
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

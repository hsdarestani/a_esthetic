// Native staff surface. Compiled into the generated Capacitor iOS target.
import SwiftUI
import Capacitor
import UIKit

final class StaffScreenState: ObservableObject {
    @Published var screen: [String: Any] = [:]
    @Published var values: [String: String] = [:]
    var send: ((String, [String: String]) -> Void)?
    func replace(_ next: [String: Any]) {
        values = [:]
        for field in (next["fields"] as? [[String: Any]] ?? []) {
            if let key = field["id"] as? String { values[key] = field["value"] as? String ?? "" }
        }
        screen = next
    }
}

struct StaffNativeScreen: View {
    @ObservedObject var state: StaffScreenState
    private let paper = Color(red: 248/255, green: 246/255, blue: 241/255)
    private let card = Color(red: 255/255, green: 253/255, blue: 250/255)
    private let ink = Color(red: 23/255, green: 41/255, blue: 35/255)
    private let green = Color(red: 35/255, green: 71/255, blue: 59/255)
    private func action(_ id: String) { state.send?(id, state.values) }
    private func items(_ key: String) -> [[String: Any]] { state.screen[key] as? [[String: Any]] ?? [] }
    private func text(_ item: [String: Any], _ key: String) -> String { item[key] as? String ?? "" }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button { action("back") } label: {
                    Image(systemName: "chevron.left").font(.headline).frame(width: 44, height: 44)
                }.accessibilityLabel("Back")
                Spacer()
                Text("A+ ESTHETIC").font(.caption.weight(.semibold)).tracking(3)
                Spacer()
                Button { action("home") } label: {
                    Image(systemName: "square.grid.2x2").font(.headline).frame(width: 44, height: 44)
                }.accessibilityLabel("Home")
            }.foregroundColor(green).padding(.horizontal, 10)
            VStack(alignment: .leading, spacing: 6) {
                Text(text(state.screen, "title")).font(.system(size: 34, weight: .regular, design: .serif))
                if !text(state.screen, "subtitle").isEmpty {
                    Text(text(state.screen, "subtitle")).font(.subheadline).foregroundColor(.secondary)
                }
                if !items("week").isEmpty {
                    HStack(spacing: 2) {
                        ForEach(Array(items("week").enumerated()), id: \.offset) { _, item in
                            Button { action(text(item, "id")) } label: {
                                Text(text(item, "label")).font(.caption.weight(.semibold))
                                    .multilineTextAlignment(.center).frame(maxWidth: .infinity).frame(minHeight: 48)
                                    .background((item["selected"] as? Bool ?? false) ? green : card)
                                    .foregroundColor((item["selected"] as? Bool ?? false) ? .white : ink)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                            }.buttonStyle(.plain)
                        }
                    }.gesture(DragGesture(minimumDistance: 25).onEnded { value in
                        if abs(value.translation.width) > abs(value.translation.height) {
                            action(value.translation.width < 0 ? "week-next" : "week-prev")
                        }
                    })
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(18).background(paper)
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if state.screen["busy"] as? Bool == true {
                        ProgressView().frame(maxWidth: .infinity).padding()
                    }
                    if !text(state.screen, "message").isEmpty {
                        Text(text(state.screen, "message")).font(.subheadline)
                            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
                            .background(card).clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    ForEach(Array(items("fields").enumerated()), id: \.offset) { _, field in
                        fieldView(field)
                    }
                    ForEach(Array(items("rows").enumerated()), id: \.offset) { _, row in
                        Button { action(text(row, "id")) } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(text(row, "label")).foregroundColor(ink).font(.headline)
                                    Text(text(row, "detail")).foregroundColor(.secondary).font(.subheadline)
                                }
                                Spacer()
                                if !text(row, "id").isEmpty { Image(systemName: "chevron.right").foregroundColor(green) }
                            }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
                                .background(card).clipShape(RoundedRectangle(cornerRadius: 14))
                        }.disabled(text(row, "id").isEmpty).buttonStyle(.plain)
                    }
                    ForEach(Array(items("actions").enumerated()), id: \.offset) { _, item in
                        Button { action(text(item, "id")) } label: {
                            Text(text(item, "label")).font(.headline).frame(maxWidth: .infinity).frame(minHeight: 50)
                                .background(green).foregroundColor(.white).clipShape(RoundedRectangle(cornerRadius: 12))
                        }.buttonStyle(.plain)
                    }
                }.padding(.horizontal, 18).padding(.bottom, 24)
            }
            HStack {
                ForEach(Array(items("tabs").enumerated()), id: \.offset) { _, tab in
                    Button { action(text(tab, "id")) } label: {
                        VStack(spacing: 5) {
                            Image(systemName: text(tab, "icon")).font(.system(size: 20))
                            Text(text(tab, "label")).font(.caption2)
                        }.frame(maxWidth: .infinity).frame(minHeight: 54)
                    }.foregroundColor(green)
                }
            }.padding(.horizontal, 8).background(card)
        }.foregroundColor(ink).background(paper.ignoresSafeArea()).preferredColorScheme(.light)
    }

    @ViewBuilder private func fieldView(_ field: [String: Any]) -> some View {
        let key = text(field, "id")
        let binding = Binding(get: { state.values[key] ?? "" }, set: { state.values[key] = $0 })
        VStack(alignment: .leading, spacing: 7) {
            Text(text(field, "label")).font(.subheadline.weight(.semibold))
            if let options = field["options"] as? [[String: Any]], !options.isEmpty {
                Picker(text(field, "label"), selection: binding) {
                    ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                        Text(text(option, "label")).tag(text(option, "value"))
                    }
                }.pickerStyle(.menu).frame(maxWidth: .infinity, alignment: .leading)
            } else {
                TextField(text(field, "label"), text: binding)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
            }
        }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(card).clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

@objc(NativeStaffPlugin)
public final class NativeStaffPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "NativeStaffPlugin"
    public let jsName = "NativeStaff"
    public let pluginMethods = [
        CAPPluginMethod(name: "present", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "render", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "dismiss", returnType: CAPPluginReturnPromise)
    ]
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
    override public func capacitorDidLoad() {
        bridge?.registerPluginInstance(NativeStaffPlugin())
    }
}

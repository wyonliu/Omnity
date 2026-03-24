import SwiftUI

/// Memory palace — search + add memories.
struct MemoryView: View {
    @State private var query = ""
    @State private var memories: [MemoryItem] = []
    @State private var loading = false
    @State private var showAdd = false
    @State private var newMemory = ""
    @State private var saving = false
    @State private var hasSearched = false
    @FocusState private var searchFocused: Bool

    private let api = APIClient.shared

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack(spacing: 10) {
                OmeOrbMini(size: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text("记忆")
                        .font(.title2.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Text(memories.isEmpty ? "搜索 Ome 的记忆" : "\(memories.count) 条记忆")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }
                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .overlay(alignment: .bottom) { Divider().background(Theme.border) }

            // Search + Add
            HStack(spacing: 8) {
                TextField("搜索记忆...", text: $query)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .background(Theme.bgInput)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .foregroundStyle(Theme.textPrimary)
                    .focused($searchFocused)
                    .onSubmit { search() }

                Button(action: { search() }) {
                    Image(systemName: "magnifyingglass")
                        .font(.body.bold())
                        .foregroundStyle(Theme.bg)
                        .frame(width: 44, height: 44)
                        .background(query.trimmingCharacters(in: .whitespaces).isEmpty
                                    ? Theme.accent.opacity(0.3) : Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(query.trimmingCharacters(in: .whitespaces).isEmpty)

                Button(action: {
                    withAnimation(.easeInOut(duration: 0.2)) { showAdd.toggle() }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }) {
                    Image(systemName: showAdd ? "xmark" : "plus")
                        .font(.body.bold())
                        .foregroundStyle(Theme.accent)
                        .frame(width: 44, height: 44)
                        .background(Theme.bgCard)
                        .clipShape(Circle())
                        .overlay(Circle().stroke(Theme.border, lineWidth: 1))
                }
            }
            .padding()

            // Add form
            if showAdd {
                VStack(spacing: 8) {
                    TextField("告诉 Ome 一件事...", text: $newMemory, axis: .vertical)
                        .lineLimit(2...4)
                        .textFieldStyle(.plain)
                        .foregroundStyle(Theme.textPrimary)

                    Button(action: addMemory) {
                        HStack(spacing: 6) {
                            if saving {
                                ProgressView()
                                    .tint(Theme.bg)
                                    .scaleEffect(0.7)
                            }
                            Text(saving ? "保存中..." : "记住")
                                .font(.subheadline.bold())
                        }
                        .foregroundStyle(Theme.bg)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 8)
                        .background(Theme.accent)
                        .clipShape(Capsule())
                    }
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .disabled(newMemory.trimmingCharacters(in: .whitespaces).isEmpty || saving)
                }
                .padding()
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cornerRadius)
                        .stroke(Theme.accent.opacity(0.5), lineWidth: 1)
                )
                .padding(.horizontal)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            // Memory list
            if loading {
                Spacer()
                ProgressView().tint(Theme.accent)
                Spacer()
            } else if memories.isEmpty {
                Spacer()
                VStack(spacing: 12) {
                    OmeOrb(size: 40, intensity: 0.3, breathing: false)
                    Text(hasSearched ? "没有找到相关记忆" : "和 Ome 聊天，记忆会自动积累")
                        .font(.body)
                        .foregroundStyle(Theme.textMuted)
                }
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(memories) { mem in
                            VStack(alignment: .leading, spacing: 8) {
                                Text(mem.text)
                                    .font(.body)
                                    .foregroundStyle(Theme.textPrimary)
                                    .lineSpacing(4)
                                if let score = mem.score {
                                    HStack(spacing: 4) {
                                        Image(systemName: "waveform")
                                            .font(.caption2)
                                        Text("相关度 \(Int(score * 100))%")
                                            .font(.caption2)
                                    }
                                    .foregroundStyle(Theme.textMuted)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(Theme.bgCard)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.cornerRadius)
                                    .stroke(Theme.border, lineWidth: 1)
                            )
                        }
                    }
                    .padding()
                }
                .refreshable { search(query: nil) }
            }
        }
        .background(Theme.bg)
        .task { search(query: "最近的记忆") }
    }

    private func search(query: String? = nil) {
        let q = query ?? self.query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return }
        hasSearched = true
        loading = true
        searchFocused = false
        Task {
            do {
                let result = try await api.recall(q)
                memories = result.results
            } catch {
                // Empty state handles it
            }
            loading = false
        }
    }

    private func addMemory() {
        let text = newMemory.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }
        saving = true
        Task {
            do {
                try await api.remember(text)
                newMemory = ""
                withAnimation { showAdd = false }
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                search(query: "最近的记忆")
            } catch {
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            }
            saving = false
        }
    }
}

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

    private let api = APIClient.shared

    var body: some View {
        VStack(spacing: 0) {
            // Header
            VStack(alignment: .leading, spacing: 4) {
                Text("🧠 记忆")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.textPrimary)
                Text(memories.isEmpty ? "搜索 Ome 的记忆" : "\(memories.count) 条记忆")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
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
                    .onSubmit { search() }

                Button(action: { search() }) {
                    Text("搜")
                        .font(.body.bold())
                        .foregroundStyle(Theme.bg)
                        .frame(width: 44, height: 44)
                        .background(Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(query.trimmingCharacters(in: .whitespaces).isEmpty)

                Button(action: { showAdd.toggle() }) {
                    Text(showAdd ? "×" : "+")
                        .font(.title2)
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
                        Text(saving ? "保存中..." : "记住")
                            .font(.subheadline.bold())
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
                        .stroke(Theme.accent, lineWidth: 1)
                )
                .padding(.horizontal)
            }

            // Memory list
            if loading {
                Spacer()
                ProgressView().tint(Theme.accent)
                Spacer()
            } else if memories.isEmpty {
                Spacer()
                VStack(spacing: 12) {
                    Text("🌊").font(.system(size: 48))
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
                                    Text("相关度 \(Int(score * 100))%")
                                        .font(.caption2)
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
        Task {
            do {
                let result = try await api.recall(q)
                memories = result.results
            } catch {
                print("Recall error:", error)
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
                showAdd = false
                search(query: "最近的记忆")
            } catch {
                print("Remember error:", error)
            }
            saving = false
        }
    }
}

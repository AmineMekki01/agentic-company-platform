import type { AgentSetting, AgentSettingCreate, DbUser } from "@/lib/api";

interface Props {
  selected: AgentSetting;
  setSelected: (a: AgentSetting) => void;
  users: DbUser[];
  toggleAllowedUser: (agent: AgentSetting | AgentSettingCreate, email: string) => void;
}

export default function DeployTab({ selected, setSelected, users, toggleAllowedUser }: Props) {
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="text-xs font-medium text-secondary">Visibility</span>
        <select
          value={selected.visibility || "all"}
          onChange={(e) => setSelected({ ...selected, visibility: e.target.value })}
          className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
        >
          <option value="all">All users</option>
          <option value="admin_only">Admins only</option>
          <option value="restricted">Restricted to specific users</option>
        </select>
      </label>

      {selected.visibility === "restricted" && (
        <div className="block">
          <span className="text-xs font-medium text-secondary">Allowed Users</span>
          <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
            {users.length === 0 && (
              <p className="text-xs text-tertiary">No users found.</p>
            )}
            {users.map((u) => {
              const checked = (selected.allowed_users || []).includes(u.email);
              const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
              return (
                <label key={u.id} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleAllowedUser(selected, u.email)}
                    className="accent-brand"
                  />
                  <span>{display}</span>
                  <span className="text-xs text-tertiary">{u.email}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      <div className="block">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-secondary">Beta Testers</span>
          {(selected.beta_users || []).length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning border border-warning/20">
              Staged
            </span>
          )}
        </div>
        <p className="text-[11px] text-tertiary mb-1">
          When beta testers are selected, only these users (and admins) can see the agent. Clear the list to release to all permitted users.
        </p>
        <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
          {users.length === 0 && (
            <p className="text-xs text-tertiary">No users found.</p>
          )}
          {users.map((u) => {
            const checked = (selected.beta_users || []).includes(u.email);
            const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
            return (
              <label key={u.id} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const current = selected.beta_users || [];
                    const next = checked
                      ? current.filter((e) => e !== u.email)
                      : [...current, u.email];
                    setSelected({ ...selected, beta_users: next });
                  }}
                  className="accent-brand"
                />
                <span>{display}</span>
                <span className="text-xs text-tertiary">{u.email}</span>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}

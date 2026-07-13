import { useEffect, useState } from "react";
import { KeyRound, Loader2, Pencil, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";
import { api, type Secret, type SecretCreate } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";
import { SECRET_TYPES, SECRET_TYPE_LABELS, SECRET_TYPE_SCHEMAS, type SecretType } from "@/lib/secretSchemas";

function SecretTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    notion: "bg-brand/10 text-brand border-brand/20",
    jira: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    s3: "bg-warning-soft text-warning border-warning/20",
    gdrive: "bg-green-500/10 text-green-400 border-green-500/20",
    custom: "bg-hover text-secondary border-line",
  };
  return (
    <span
      className={
        "text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border " +
        (colors[type.toLowerCase()] || "bg-hover text-secondary border-line")
      }
    >
      {SECRET_TYPE_LABELS[type as SecretType] || type}
    </span>
  );
}

const inputClass =
  "w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition";

interface CustomField {
  key: string;
  value: string;
}

function CredentialFields({
  secretType,
  values,
  onChange,
  customFields,
  onCustomFieldsChange,
  isEdit,
}: {
  secretType: SecretType;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  customFields: CustomField[];
  onCustomFieldsChange: (fields: CustomField[]) => void;
  isEdit: boolean;
}) {
  const schema = SECRET_TYPE_SCHEMAS[secretType];

  if (!schema) {
    // custom type: freeform key/value rows
    return (
      <div className="space-y-2">
        {customFields.map((f, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={f.key}
              onChange={(e) => {
                const next = [...customFields];
                next[i] = { ...next[i], key: e.target.value };
                onCustomFieldsChange(next);
              }}
              placeholder="Key"
              className={inputClass}
            />
            <input
              value={f.value}
              onChange={(e) => {
                const next = [...customFields];
                next[i] = { ...next[i], value: e.target.value };
                onCustomFieldsChange(next);
              }}
              placeholder={isEdit ? "Leave blank to keep current value" : "Value"}
              type="password"
              className={inputClass}
            />
            <button
              type="button"
              onClick={() => onCustomFieldsChange(customFields.filter((_, idx) => idx !== i))}
              className="shrink-0 rounded-md p-2 text-tertiary hover:text-danger hover:bg-danger-soft transition"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => onCustomFieldsChange([...customFields, { key: "", value: "" }])}
          className="flex items-center gap-1.5 text-xs text-brand hover:underline"
        >
          <Plus className="h-3 w-3" />
          Add field
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {schema.map((field) => (
        <input
          key={field.key}
          value={values[field.key] ?? ""}
          onChange={(e) => onChange(field.key, e.target.value)}
          placeholder={
            field.label + (field.required ? "" : " (optional)") + (isEdit && field.sensitive ? " — leave blank to keep current value" : "")
          }
          type={field.sensitive ? "password" : "text"}
          className={inputClass}
        />
      ))}
    </div>
  );
}

export default function AdminSecrets() {
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ slug: "", name: "", secret_type: "jira" as SecretType });
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [formCustomFields, setFormCustomFields] = useState<CustomField[]>([]);

  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [editCustomFields, setEditCustomFields] = useState<CustomField[]>([]);
  const [editSecretType, setEditSecretType] = useState<SecretType>("jira");

  const refresh = async () => {
    setLoading(true);
    try {
      setSecrets(await api.listSecrets());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const resetForm = () => {
    setForm({ slug: "", name: "", secret_type: "jira" });
    setFormValues({});
    setFormCustomFields([]);
  };

  const buildCredentials = (values: Record<string, string>, customFields: CustomField[], secretType: SecretType) => {
    if (!SECRET_TYPE_SCHEMAS[secretType]) {
      return Object.fromEntries(customFields.filter((f) => f.key.trim()).map((f) => [f.key.trim(), f.value]));
    }
    return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== ""));
  };

  const create = async () => {
    if (!form.slug.trim() || !form.name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const body: SecretCreate = {
        slug: form.slug,
        name: form.name,
        secret_type: form.secret_type,
        credentials: buildCredentials(formValues, formCustomFields, form.secret_type),
      };
      await api.createSecret(body);
      setShowForm(false);
      resetForm();
      await refresh();
    } catch (e: any) {
      setError(e.message || "Failed to create secret");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = async (secret: Secret) => {
    setError(null);
    const detail = await api.getSecret(secret.slug);
    setEditingSlug(secret.slug);
    setEditName(detail.name);
    setEditSecretType(detail.secret_type as SecretType);
    setEditValues(detail.non_sensitive_credentials as Record<string, string>);
    setEditCustomFields([]);
  };

  const saveEdit = async () => {
    if (!editingSlug) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateSecret(editingSlug, {
        name: editName,
        credentials: buildCredentials(editValues, editCustomFields, editSecretType),
      });
      setEditingSlug(null);
      await refresh();
    } catch (e: any) {
      setError(e.message || "Failed to update secret");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (slug: string) => {
    if (!confirm("Delete this secret?")) return;
    setError(null);
    try {
      await api.deleteSecret(slug);
      await refresh();
    } catch (e: any) {
      setError(e.message || "Failed to delete secret");
    }
  };

  return (
    <div>
      <AdminPageHeader
        title="Secrets"
        description="Store credentials once, reference them from any number of connectors"
        icon={KeyRound}
        iconColor="text-amber-400"
        iconBg="bg-amber-500/10"
      >
        <button
          onClick={() => {
            setShowForm((s) => !s);
            setEditingSlug(null);
          }}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
        >
          <Plus className="h-3.5 w-3.5" />
          {showForm ? "Cancel" : "Add Secret"}
        </button>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-2 rounded-lg transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger-soft text-danger text-sm px-4 py-2.5 mb-4">
          {error}
        </div>
      )}

      {showForm && (
        <div className="rounded-2xl border border-line/60 bg-card p-5 mb-6 space-y-3 max-w-lg shadow-sm">
          <h2 className="font-medium text-primary">New Secret</h2>
          <input
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="Slug (e.g. company-aws)"
            className={inputClass}
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name (e.g. Company AWS Account)"
            className={inputClass}
          />
          <select
            value={form.secret_type}
            onChange={(e) => {
              setForm({ ...form, secret_type: e.target.value as SecretType });
              setFormValues({});
              setFormCustomFields([]);
            }}
            className={inputClass}
          >
            {SECRET_TYPES.map((t) => (
              <option key={t} value={t}>
                {SECRET_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
          <CredentialFields
            secretType={form.secret_type}
            values={formValues}
            onChange={(key, value) => setFormValues({ ...formValues, [key]: value })}
            customFields={formCustomFields}
            onCustomFieldsChange={setFormCustomFields}
            isEdit={false}
          />
          <button
            onClick={create}
            disabled={saving}
            className="flex items-center gap-1.5 bg-success hover:bg-success-hover disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-success/15"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Secret
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-tertiary text-sm py-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading secrets…
        </div>
      )}

      <div className="space-y-2">
        {secrets.map((s) => (
          <div key={s.id} className="bg-card border border-line rounded-xl px-4 py-3 transition hover:border-line">
            {editingSlug === s.slug ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-primary">Edit "{s.name}"</span>
                  <button onClick={() => setEditingSlug(null)} className="rounded-md p-1.5 text-tertiary hover:bg-hover transition">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" className={inputClass} />
                <CredentialFields
                  secretType={editSecretType}
                  values={editValues}
                  onChange={(key, value) => setEditValues({ ...editValues, [key]: value })}
                  customFields={editCustomFields}
                  onCustomFieldsChange={setEditCustomFields}
                  isEdit={true}
                />
                <button
                  onClick={saveEdit}
                  disabled={saving}
                  className="flex items-center gap-1.5 bg-success hover:bg-success-hover disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save Changes
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-canvas border border-line">
                    <KeyRound className="h-5 w-5 text-tertiary" />
                  </div>
                  <div>
                    <div className="font-medium text-primary flex items-center gap-2">
                      {s.name}
                      <SecretTypeBadge type={s.secret_type} />
                    </div>
                    <div className="text-xs text-tertiary">
                      {s.slug} · used by {s.connector_count} connector{s.connector_count === 1 ? "" : "s"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => startEdit(s)}
                    className="rounded-md p-2 text-tertiary hover:text-brand hover:bg-brand/10 transition"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => remove(s.slug)}
                    className="rounded-md p-2 text-tertiary hover:text-danger hover:bg-danger-soft transition"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
        {!loading && secrets.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-tertiary">
            <KeyRound className="h-10 w-10 text-tertiary mb-3" />
            <p className="text-sm">No secrets configured yet</p>
          </div>
        )}
      </div>
    </div>
  );
}

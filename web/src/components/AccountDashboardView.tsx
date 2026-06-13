import { useEffect, useState } from "react";
import { RefreshCw, Search, Send, Trash2, UserPlus, UsersRound } from "lucide-react";
import type { TryOpsClient } from "../api";
import type {
  AccountDashboard,
  AccountInvitation,
  AccountMember,
  AccountQuota,
  AuthSession,
  JobConcurrency,
  UserProfile,
  VtonJobRecord
} from "../types";
import { formatNumber, formatOptionalMs } from "../format";
import { JobStatusList } from "./JobStatusList";
import { MetricTile } from "./MetricTile";
import { RecentTryOnGallery } from "./RecentTryOnGallery";

interface AccountDashboardViewProps {
  client: TryOpsClient;
  dashboard?: AccountDashboard;
  jobs: VtonJobRecord[];
  jobConcurrency?: JobConcurrency;
  invitations: AccountInvitation[];
  quota?: AccountQuota;
  members: AccountMember[];
  session?: AuthSession;
  onCreateWorkspace: (payload: { name: string; description?: string }) => Promise<void>;
  onInviteMember: (email: string, role: string) => Promise<void>;
  onRefresh: () => void;
  onRemoveMember: (memberId: string) => Promise<void>;
  onRevokeInvitation: (invitationId: string) => Promise<void>;
  onSearchProfiles: (query: string) => Promise<UserProfile[]>;
  onUpdateMember: (memberId: string, payload: { role?: string; status?: string }) => Promise<void>;
  onUpdateWorkspace: (accountId: string, payload: { name?: string; description?: string }) => Promise<void>;
}

export function AccountDashboardView({
  client,
  dashboard,
  jobs,
  jobConcurrency,
  invitations,
  quota,
  members,
  session,
  onCreateWorkspace,
  onInviteMember,
  onRefresh,
  onRemoveMember,
  onRevokeInvitation,
  onSearchProfiles,
  onUpdateMember,
  onUpdateWorkspace
}: AccountDashboardViewProps) {
  const account = dashboard?.account ?? quota?.account;
  const recent = dashboard?.recent_requests ?? [];
  const canManage = Boolean(session?.permissions.can_manage_account);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDescription, setWorkspaceDescription] = useState("");
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("account_member");
  const [searchQuery, setSearchQuery] = useState("");
  const [profiles, setProfiles] = useState<UserProfile[]>([]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | undefined>();
  const activeMemberEmails = new Set(members.map((member) => (member.email ?? "").trim().toLowerCase()).filter(Boolean));
  const activeMemberSubjects = new Set(members.map((member) => member.subject).filter(Boolean));
  const normalizedInviteEmail = inviteEmail.trim().toLowerCase();
  const inviteTargetsExistingMember = Boolean(normalizedInviteEmail && activeMemberEmails.has(normalizedInviteEmail));
  const visibleProfiles = profiles.filter((profile) => {
    const email = (profile.email ?? "").trim().toLowerCase();
    return !activeMemberSubjects.has(profile.subject) && (!email || !activeMemberEmails.has(email));
  });
  const jobSlotActive = jobConcurrency?.active ?? jobs.length;
  const jobSlotLimit = jobConcurrency?.limit;
  const jobSlotRemaining = jobConcurrency?.remaining ?? 0;
  const jobSlotValue = jobSlotLimit === undefined ? `${jobSlotActive} active` : `${jobSlotActive} / ${jobSlotLimit}`;
  const jobSlotTone = jobSlotLimit !== undefined && jobSlotActive >= jobSlotLimit
    ? "red"
    : jobSlotActive > 0
      ? "amber"
      : "green";

  useEffect(() => {
    setWorkspaceName(account?.name ?? "");
    setWorkspaceDescription(account?.description ?? "");
  }, [account?.description, account?.name]);

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setActionError(undefined);
    try {
      await action();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Workspace action failed");
    } finally {
      setBusy(false);
    }
  }

  async function searchPeople() {
    if (searchQuery.trim().length < 2) {
      setProfiles([]);
      return;
    }
    await runAction(async () => {
      setProfiles(await onSearchProfiles(searchQuery));
    });
  }

  return (
    <section className="account-page">
      <div className="account-hero">
        <div className="account-hero-identity">
          {account?.avatar_url ? <img alt="" className="account-avatar large" src={account.avatar_url} /> : null}
          <div>
          <p className="eyebrow">My Account</p>
          <h2>{account?.name ?? "My wardrobe"}</h2>
          <p>{account ? `${account.plan} plan · ${account.status}` : "Sign in to save looks and view fitting history."}</p>
          </div>
        </div>
        <button className="text-button" onClick={onRefresh} type="button">
          <RefreshCw aria-hidden="true" size={16} />
          Refresh
        </button>
      </div>

      <div className="metric-grid">
        <MetricTile label="Requests" value={dashboard?.usage.total_requests ?? 0} tone="blue" />
        <MetricTile label="Try-ons" value={dashboard?.usage.vton.requests ?? 0} tone="green" />
        <MetricTile label="VTON latency" value={formatOptionalMs(dashboard?.usage.vton.avg_latency_ms)} tone="amber" />
        <MetricTile label="Quota used" value={`${formatNumber(quota?.utilization_pct ?? dashboard?.quota.utilization_pct ?? 0)}%`} tone="blue" />
        <MetricTile
          detail={jobConcurrency ? `${jobConcurrency.plan} plan · ${jobSlotRemaining} free` : "workspace active jobs"}
          label="Job slots"
          tone={jobSlotTone}
          value={jobSlotValue}
        />
      </div>

      <div className="account-grid">
        <section className="panel panel-wide">
          <div className="panel-header compact">
            <h2>Running jobs</h2>
            <span className="status-pill blue">
              {jobConcurrency ? `${jobConcurrency.active} / ${jobConcurrency.limit} active` : `${jobs.length} active`}
            </span>
          </div>
          {jobConcurrency ? (
            <p className="job-concurrency-note">
              {jobConcurrency.plan} plan capacity · {jobConcurrency.remaining} slot{jobConcurrency.remaining === 1 ? "" : "s"} available · {jobConcurrency.global_workers ?? 1} global worker{jobConcurrency.global_workers === 1 ? "" : "s"}
            </p>
          ) : null}
          <JobStatusList client={client} jobs={jobs} emptyText="No active try-on jobs in this workspace." />
        </section>

        <section className="panel account-quota-panel">
          <div className="panel-header compact">
            <h2>Workspace profile</h2>
            <span className="status-pill neutral">{session?.membership?.role ?? "member"}</span>
          </div>
          <div className="workspace-form">
            <label className="field">
              <span>Name</span>
              <input disabled={!canManage || busy} onChange={(event) => setWorkspaceName(event.target.value)} value={workspaceName} />
            </label>
            <label className="field">
              <span>Description</span>
              <input disabled={!canManage || busy} onChange={(event) => setWorkspaceDescription(event.target.value)} value={workspaceDescription} />
            </label>
            <button
              className="text-button"
              disabled={!canManage || busy || !account}
              onClick={() => account && runAction(() => onUpdateWorkspace(account.id, { name: workspaceName, description: workspaceDescription }))}
              type="button"
            >
              Save workspace
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header compact">
            <h2>Create workspace</h2>
            <UserPlus aria-hidden="true" size={18} />
          </div>
          <div className="workspace-form">
            <label className="field">
              <span>Name</span>
              <input disabled={busy} onChange={(event) => setNewWorkspaceName(event.target.value)} placeholder="Studio team" value={newWorkspaceName} />
            </label>
            <label className="field">
              <span>Description</span>
              <input disabled={busy} onChange={(event) => setNewWorkspaceDescription(event.target.value)} placeholder="Campaign, team, or client workspace" value={newWorkspaceDescription} />
            </label>
            <button
              className="text-button"
              disabled={busy || !newWorkspaceName.trim()}
              onClick={() => runAction(async () => {
                await onCreateWorkspace({ name: newWorkspaceName, description: newWorkspaceDescription });
                setNewWorkspaceName("");
                setNewWorkspaceDescription("");
              })}
              type="button"
            >
              Create
            </button>
          </div>
        </section>

        <section className="panel account-quota-panel">
          <div className="panel-header compact">
            <h2>Usage and quota</h2>
            <span className="status-pill green">{quota?.period ?? dashboard?.quota.period ?? "today"}</span>
          </div>
          <div className="quota-bars">
            {jobConcurrency ? (
              <div className="quota-bar job-slot-quota">
                <div>
                  <strong>Active VTON Jobs</strong>
                  <span>{jobConcurrency.active} / {jobConcurrency.limit}</span>
                </div>
                <meter max={jobConcurrency.limit} value={jobConcurrency.active} />
                <small>
                  {jobConcurrency.plan} plan concurrent job limit · {jobConcurrency.remaining} slot{jobConcurrency.remaining === 1 ? "" : "s"} available
                </small>
              </div>
            ) : null}
            {(quota?.dimensions ?? dashboard?.quota.dimensions ?? []).map((dimension) => (
              <div className="quota-bar" key={dimension.dimension}>
                <div>
                  <strong>{labelDimension(dimension.dimension)}</strong>
                  <span>{formatNumber(dimension.used)} / {formatNumber(dimension.limit)}</span>
                </div>
                <meter max={dimension.limit} value={dimension.used} />
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header compact">
            <h2>Members</h2>
            <UsersRound aria-hidden="true" size={18} />
          </div>
          <div className="member-list">
            {members.length === 0 ? (
              <p className="empty-state">No members loaded.</p>
            ) : (
              members.map((member) => (
                <div className="member-row" key={member.id}>
                  <span className="person-line">
                    {member.avatar_url ? (
                      <img alt="" className="member-avatar" src={member.avatar_url} />
                    ) : (
                      <span className="member-avatar fallback">{initialFor(member.display_name || member.email || member.subject)}</span>
                    )}
                    <span>
                      <strong>{member.display_name || member.email || member.subject}</strong>
                      {member.email ? <small>{member.email}</small> : null}
                    </span>
                  </span>
                  {canManage ? (
                    <div className="member-actions">
                      <select
                        disabled={busy}
                        onChange={(event) => runAction(() => onUpdateMember(member.id, { role: event.target.value }))}
                        value={member.role}
                      >
                        <option value="account_owner">Owner</option>
                        <option value="account_member">Member</option>
                        <option value="account_viewer">Viewer</option>
                      </select>
                      <button className="icon-button" disabled={busy} onClick={() => runAction(() => onRemoveMember(member.id))} title="Remove member" type="button">
                        <Trash2 aria-hidden="true" size={15} />
                      </button>
                    </div>
                  ) : (
                    <strong>{member.role}</strong>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="panel-header compact">
            <h2>Invite people</h2>
            <span className="status-pill neutral">{invitations.filter((item) => item.status === "pending").length} pending</span>
          </div>
          <div className="invite-grid">
            <div className="workspace-form">
              <label className="field">
                <span>Search users</span>
                <input disabled={!canManage || busy} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Name or email" value={searchQuery} />
              </label>
              <button className="text-button" disabled={!canManage || busy || searchQuery.trim().length < 2} onClick={searchPeople} type="button">
                <Search aria-hidden="true" size={16} />
                Search
              </button>
              <div className="profile-results">
                {visibleProfiles.map((profile) => (
                  <button
                    disabled={!canManage || busy}
                    key={profile.subject}
                    onClick={() => setInviteEmail(profile.email ?? "")}
                    type="button"
                  >
                    {profile.avatar_url ? (
                      <img alt="" className="member-avatar" src={profile.avatar_url} />
                    ) : (
                      <span className="member-avatar fallback">{initialFor(profile.display_name || profile.email || profile.username || "TryOps")}</span>
                    )}
                    <span>
                      <span>{profile.display_name || profile.username || profile.email}</span>
                      <strong>{profile.email}</strong>
                    </span>
                  </button>
                ))}
                {profiles.length > 0 && visibleProfiles.length === 0 ? (
                  <p className="form-note">All matching users are already members of this workspace.</p>
                ) : null}
              </div>
            </div>
            <div className="workspace-form">
              <label className="field">
                <span>Email</span>
                <input disabled={!canManage || busy} onChange={(event) => setInviteEmail(event.target.value)} placeholder="teammate@example.com" value={inviteEmail} />
              </label>
              {inviteTargetsExistingMember ? <p className="form-note warning">This email is already a workspace member.</p> : null}
              <label className="field">
                <span>Role</span>
                <select disabled={!canManage || busy} onChange={(event) => setInviteRole(event.target.value)} value={inviteRole}>
                  <option value="account_member">Member</option>
                  <option value="account_viewer">Viewer</option>
                  <option value="account_owner">Owner</option>
                </select>
              </label>
              <button
                className="text-button"
                disabled={!canManage || busy || !inviteEmail.trim() || inviteTargetsExistingMember}
                onClick={() => runAction(async () => {
                  await onInviteMember(inviteEmail, inviteRole);
                  setInviteEmail("");
                })}
                type="button"
              >
                <Send aria-hidden="true" size={16} />
                Invite
              </button>
            </div>
          </div>
          {invitations.length > 0 ? (
            <div className="invitation-list">
              {invitations.map((invitation) => (
                <div className="member-row" key={invitation.id}>
                  <span className="person-line">
                    <span className="member-avatar fallback">{initialFor(invitation.email)}</span>
                    <span>
                      <strong>{invitation.email}</strong>
                      <small>{invitation.status}</small>
                    </span>
                  </span>
                  <strong>{invitation.role} · {invitation.status}</strong>
                  {canManage && invitation.status === "pending" ? (
                    <button className="icon-button" disabled={busy} onClick={() => runAction(() => onRevokeInvitation(invitation.id))} title="Revoke invitation" type="button">
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          {actionError ? <div className="asset-error">{actionError}</div> : null}
        </section>

        <section className="panel panel-wide">
          <div className="panel-header compact">
            <h2>Saved looks</h2>
            <span className="status-pill neutral">{recent.length}</span>
          </div>
          <RecentTryOnGallery client={client} requests={recent} limit={12} />
        </section>
      </div>
    </section>
  );
}

function labelDimension(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function initialFor(value: string): string {
  return (value.trim().match(/[A-Za-z0-9]/)?.[0] ?? "T").toUpperCase();
}

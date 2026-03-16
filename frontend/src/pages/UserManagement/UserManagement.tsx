import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, KeyRound, Plus, Shield, Trash2, UserCog, UserRoundCheck, UserRoundX } from 'lucide-react';

import { type UserCreateRequest, type UserItem, type UserRole, userApi } from '../../api/client';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { notifyError, notifySuccess } from '../../utils/notify';
import './UserManagement.css';

const roleLabelMap: Record<UserRole, string> = {
  admin: '管理员',
  member: '成员',
  viewer: '访客',
};

function roleClassName(role: UserRole) {
  return role === 'admin' ? 'badge-blue' : role === 'member' ? 'badge-green' : 'badge-yellow';
}

export default function UserManagement() {
  const [pageSize, setPageSize] = useState(10);
  const qc = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserItem | null>(null);
  const [resetPwdUser, setResetPwdUser] = useState<UserItem | null>(null);
  const [deleteUser, setDeleteUser] = useState<UserItem | null>(null);
  const [confirmBatchStatus, setConfirmBatchStatus] = useState<boolean | null>(null);
  const [confirmBatchDelete, setConfirmBatchDelete] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | UserRole>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [sortBy, setSortBy] = useState<'created_at' | 'username' | 'role' | 'is_active'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [jumpPageInput, setJumpPageInput] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [newPassword, setNewPassword] = useState('');
  const [form, setForm] = useState<UserCreateRequest>({
    username: '',
    password: '',
    role: 'member',
    is_active: true,
  });

  const { data: userListData, isLoading } = useQuery({
    queryKey: ['users', page, keyword, roleFilter, statusFilter, sortBy, sortOrder, pageSize],
    queryFn: () => userApi.list({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      keyword: keyword.trim() || undefined,
      role: roleFilter === 'all' ? undefined : roleFilter,
      is_active: statusFilter === 'all' ? undefined : statusFilter === 'active',
      sort_by: sortBy,
      sort_order: sortOrder,
    }),
  });
  const users = useMemo(() => userListData?.items ?? [], [userListData?.items]);
  const total = userListData?.total ?? 0;

  const createMutation = useMutation({
    mutationFn: userApi.create,
    onSuccess: () => {
      notifySuccess('用户创建成功');
      setForm({ username: '', password: '', role: 'member', is_active: true });
      setIsCreateOpen(false);
      qc.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err: Error) => notifyError(`创建失败：${err.message}`),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { role?: UserRole; is_active?: boolean } }) =>
      userApi.update(id, payload),
    onSuccess: () => {
      notifySuccess('用户信息已更新');
      setSelectedUser(null);
      qc.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err: Error) => notifyError(`更新失败：${err.message}`),
  });

  const resetMutation = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) => userApi.resetPassword(id, password),
    onSuccess: () => {
      notifySuccess('密码重置成功');
      setNewPassword('');
      setResetPwdUser(null);
    },
    onError: (err: Error) => notifyError(`重置失败：${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => userApi.remove(id),
    onSuccess: () => {
      notifySuccess('用户已删除');
      setDeleteUser(null);
      qc.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err: Error) => notifyError(`删除失败：${err.message}`),
  });

  const batchStatusMutation = useMutation({
    mutationFn: ({ ids, isActive }: { ids: string[]; isActive: boolean }) => userApi.batchStatus(ids, isActive),
    onSuccess: (res) => {
      notifySuccess(res.message);
      setSelectedIds([]);
      setConfirmBatchStatus(null);
      qc.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err: Error) => notifyError(`批量操作失败：${err.message}`),
  });

  const batchDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => userApi.batchDelete(ids),
    onSuccess: (res) => {
      notifySuccess(res.message);
      setSelectedIds([]);
      setConfirmBatchDelete(false);
      qc.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err: Error) => notifyError(`批量删除失败：${err.message}`),
  });

  const stats = useMemo(() => {
    const currentPageCount = users.length;
    const active = users.filter((u) => u.is_active).length;
    const admins = users.filter((u) => u.role === 'admin').length;
    return { currentPageCount, active, admins };
  }, [users]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasNextPage = page < totalPages;
  const selectedOnPage = users.filter((u) => selectedIds.includes(u.id)).length;
  const allOnPageSelected = users.length > 0 && selectedOnPage === users.length;

  const handleExportCsv = async () => {
    try {
      const allRows: UserItem[] = [];
      let skip = 0;
      const batch = 200;
      while (true) {
        const res = await userApi.list({
          skip,
          limit: batch,
          keyword: keyword.trim() || undefined,
          role: roleFilter === 'all' ? undefined : roleFilter,
          is_active: statusFilter === 'all' ? undefined : statusFilter === 'active',
          sort_by: sortBy,
          sort_order: sortOrder,
        });
        allRows.push(...res.items);
        skip += res.items.length;
        if (skip >= res.total || res.items.length === 0) break;
      }

      const header = ['username', 'role', 'is_active', 'created_at', 'updated_at'];
      const lines = [header.join(',')];
      for (const item of allRows) {
        const row = [
          item.username,
          item.role,
          item.is_active ? 'true' : 'false',
          item.created_at,
          item.updated_at,
        ].map((field) => `"${String(field).replace(/"/g, '""')}"`);
        lines.push(row.join(','));
      }
      const csv = lines.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `users-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      notifySuccess(`导出完成，共 ${allRows.length} 条`);
    } catch (err) {
      const message = err instanceof Error ? err.message : '未知错误';
      notifyError(`导出失败：${message}`);
    }
  };

  return (
    <div className="user-page">
      <section className="user-hero">
        <div>
          <div className="user-hero-pill"><UserCog size={13} /> Team Access</div>
          <h1>用户与权限管理</h1>
          <p>管理团队账号、角色与状态，确保多人协作可控且安全。</p>
        </div>
        <button className="btn btn-primary" onClick={() => setIsCreateOpen(true)}>
          <Plus size={16} /> 新建用户
        </button>
      </section>

      <section className="user-stats">
        <div className="user-stat"><span>当前页数量</span><strong>{stats.currentPageCount}</strong></div>
        <div className="user-stat"><span>已启用</span><strong>{stats.active}</strong></div>
        <div className="user-stat"><span>管理员</span><strong>{stats.admins}</strong></div>
      </section>

      <section className="user-list card">
        <div className="user-list-header">
          <h2>账号列表</h2>
          <button className="btn btn-ghost btn-sm" onClick={handleExportCsv}>
            <Download size={14} /> 导出 CSV
          </button>
        </div>
        <div className="user-filters">
          <input
            className="form-input"
            placeholder="搜索用户名"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
              setSelectedIds([]);
            }}
          />
          <select
            className="form-input app-select"
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value as 'all' | UserRole);
              setPage(1);
            }}
          >
            <option value="all">全部角色</option>
            <option value="admin">管理员</option>
            <option value="member">成员</option>
            <option value="viewer">访客</option>
          </select>
          <select
            className="form-input app-select"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as 'all' | 'active' | 'inactive');
              setPage(1);
              setSelectedIds([]);
            }}
          >
            <option value="all">全部状态</option>
            <option value="active">仅启用</option>
            <option value="inactive">仅禁用</option>
          </select>
          <select
            className="form-input app-select"
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value as 'created_at' | 'username' | 'role' | 'is_active');
              setPage(1);
              setSelectedIds([]);
            }}
          >
            <option value="created_at">按创建时间</option>
            <option value="username">按用户名</option>
            <option value="role">按角色</option>
            <option value="is_active">按状态</option>
          </select>
          <select
            className="form-input app-select"
            value={sortOrder}
            onChange={(e) => {
              setSortOrder(e.target.value as 'asc' | 'desc');
              setPage(1);
              setSelectedIds([]);
            }}
          >
            <option value="asc">升序</option>
            <option value="desc">降序</option>
          </select>
        </div>
        <div className="user-batch-bar">
          <label className="user-checkbox">
            <input
              type="checkbox"
              checked={allOnPageSelected}
              onChange={(e) => {
                if (e.target.checked) {
                  setSelectedIds((prev) => Array.from(new Set([...prev, ...users.map((u) => u.id)])));
                } else {
                  setSelectedIds((prev) => prev.filter((id) => !users.some((u) => u.id === id)));
                }
              }}
            />
            本页全选
          </label>
          <span className="user-selected-tip">已选 {selectedIds.length} 个</span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={selectedIds.length === 0 || batchStatusMutation.isPending}
            onClick={() => setConfirmBatchStatus(true)}
          >
            批量启用
          </button>
          <button
            className="btn btn-ghost btn-sm"
            disabled={selectedIds.length === 0 || batchStatusMutation.isPending}
            onClick={() => setConfirmBatchStatus(false)}
          >
            批量禁用
          </button>
          <button
            className="btn btn-danger btn-sm"
            disabled={selectedIds.length === 0 || batchDeleteMutation.isPending}
            onClick={() => setConfirmBatchDelete(true)}
          >
            批量删除
          </button>
        </div>

        {isLoading ? (
          <div className="loading">加载用户中...</div>
        ) : users.length === 0 ? (
          <div className="loading">暂无用户</div>
        ) : (
          <div className="user-grid">
            {users.map((u) => (
              <div key={u.id} className="user-card">
                <div className="user-card-top">
                  <input
                    type="checkbox"
                    className="user-row-checkbox"
                    checked={selectedIds.includes(u.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedIds((prev) => [...prev, u.id]);
                      } else {
                        setSelectedIds((prev) => prev.filter((id) => id !== u.id));
                      }
                    }}
                  />
                  <div className="user-avatar">{u.username.slice(0, 1).toUpperCase()}</div>
                  <div className="user-meta">
                    <div className="user-name">{u.username}</div>
                    <div className="user-created">{new Date(u.created_at).toLocaleString('zh-CN')}</div>
                  </div>
                  <span className={`badge ${roleClassName(u.role)}`}>{roleLabelMap[u.role]}</span>
                </div>
                <div className="user-card-bottom">
                  <span className={`user-status ${u.is_active ? 'active' : 'inactive'}`}>
                    {u.is_active ? <UserRoundCheck size={14} /> : <UserRoundX size={14} />}
                    {u.is_active ? '已启用' : '已禁用'}
                  </span>
                  <div className="user-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => setSelectedUser(u)}>
                      <Shield size={14} /> 权限
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setResetPwdUser(u)}>
                      <KeyRound size={14} /> 重置密码
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => setDeleteUser(u)}>
                      <Trash2 size={14} /> 删除
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="user-pagination">
          <span className="user-page-total">共 {total} 条 / {totalPages} 页</span>
          <select
            className="form-input user-page-size app-select"
            value={pageSize}
            onChange={(e) => {
              const next = Number(e.target.value) || 10;
              setPageSize(next);
              setPage(1);
              setJumpPageInput('');
            }}
          >
            <option value={10}>10 / 页</option>
            <option value={20}>20 / 页</option>
            <option value={50}>50 / 页</option>
          </select>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page <= 1 || isLoading}
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
          >
            上一页
          </button>
          <span className="user-page-indicator">第 {page} / {totalPages} 页</span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={!hasNextPage || isLoading}
            onClick={() => setPage((prev) => prev + 1)}
          >
            下一页
          </button>
          <input
            className="form-input user-page-jump"
            placeholder="页码"
            value={jumpPageInput}
            onChange={(e) => setJumpPageInput(e.target.value.replace(/[^\d]/g, ''))}
          />
          <button
            className="btn btn-ghost btn-sm"
            disabled={!jumpPageInput || isLoading}
            onClick={() => {
              const parsed = Number(jumpPageInput);
              if (!parsed) return;
              const clamped = Math.min(Math.max(parsed, 1), totalPages);
              setPage(clamped);
              setJumpPageInput('');
            }}
          >
            跳转
          </button>
        </div>
      </section>

      {isCreateOpen && (
        <div className="modal-overlay" onClick={() => !createMutation.isPending && setIsCreateOpen(false)}>
          <div className="modal user-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h2 className="modal-title">新建用户</h2></div>
            <div className="p-4 flex flex-col gap-3">
              <input className="form-input" placeholder="用户名" value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
              <input className="form-input" type="password" placeholder="登录密码（至少 6 位）" value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
              <select className="form-input app-select" value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserRole }))}>
                <option value="member">成员</option>
                <option value="viewer">访客</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setIsCreateOpen(false)} disabled={createMutation.isPending}>取消</button>
              <button
                className="btn btn-primary"
                disabled={!form.username.trim() || form.password.length < 6 || createMutation.isPending}
                onClick={() => createMutation.mutate({ ...form, username: form.username.trim() })}
              >
                {createMutation.isPending ? '创建中...' : '确认创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedUser && (
        <div className="modal-overlay" onClick={() => !updateMutation.isPending && setSelectedUser(null)}>
          <div className="modal user-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h2 className="modal-title">编辑权限</h2></div>
            <div className="p-4 flex flex-col gap-3">
              <div className="text-sm text-secondary">用户：<strong>{selectedUser.username}</strong></div>
              <select className="form-input app-select" value={selectedUser.role}
                onChange={(e) => setSelectedUser((u) => (u ? { ...u, role: e.target.value as UserRole } : u))}>
                <option value="member">成员</option>
                <option value="viewer">访客</option>
                <option value="admin">管理员</option>
              </select>
              <label className="user-checkbox">
                <input type="checkbox" checked={selectedUser.is_active}
                  onChange={(e) => setSelectedUser((u) => (u ? { ...u, is_active: e.target.checked } : u))} />
                启用该账号
              </label>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setSelectedUser(null)} disabled={updateMutation.isPending}>取消</button>
              <button
                className="btn btn-primary"
                disabled={updateMutation.isPending}
                onClick={() => updateMutation.mutate({
                  id: selectedUser.id,
                  payload: { role: selectedUser.role, is_active: selectedUser.is_active },
                })}
              >
                {updateMutation.isPending ? '保存中...' : '保存修改'}
              </button>
            </div>
          </div>
        </div>
      )}

      {resetPwdUser && (
        <div className="modal-overlay" onClick={() => !resetMutation.isPending && setResetPwdUser(null)}>
          <div className="modal user-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h2 className="modal-title">重置密码</h2></div>
            <div className="p-4 flex flex-col gap-3">
              <div className="text-sm text-secondary">用户：<strong>{resetPwdUser.username}</strong></div>
              <input
                className="form-input"
                type="password"
                placeholder="输入新密码（至少 6 位）"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setResetPwdUser(null)} disabled={resetMutation.isPending}>取消</button>
              <button
                className="btn btn-primary"
                disabled={newPassword.length < 6 || resetMutation.isPending}
                onClick={() => resetMutation.mutate({ id: resetPwdUser.id, password: newPassword })}
              >
                {resetMutation.isPending ? '提交中...' : '确认重置'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteUser}
        title="删除用户"
        description={deleteUser ? `确认删除用户 ${deleteUser.username} 吗？该操作不可恢复。` : ''}
        confirmText="确认删除"
        danger
        loading={deleteMutation.isPending}
        onCancel={() => setDeleteUser(null)}
        onConfirm={() => {
          if (!deleteUser) return;
          deleteMutation.mutate(deleteUser.id);
        }}
      />

      <ConfirmDialog
        open={confirmBatchStatus !== null}
        title={confirmBatchStatus ? '批量启用账号' : '批量禁用账号'}
        description={`确认对已选 ${selectedIds.length} 个账号执行${confirmBatchStatus ? '启用' : '禁用'}吗？`}
        confirmText={confirmBatchStatus ? '确认启用' : '确认禁用'}
        loading={batchStatusMutation.isPending}
        onCancel={() => setConfirmBatchStatus(null)}
        onConfirm={() => {
          if (confirmBatchStatus === null) return;
          batchStatusMutation.mutate({ ids: selectedIds, isActive: confirmBatchStatus });
        }}
      />

      <ConfirmDialog
        open={confirmBatchDelete}
        title="批量删除用户"
        description={`确认删除已选 ${selectedIds.length} 个账号吗？该操作不可恢复。`}
        confirmText="确认批量删除"
        danger
        loading={batchDeleteMutation.isPending}
        onCancel={() => setConfirmBatchDelete(false)}
        onConfirm={() => batchDeleteMutation.mutate(selectedIds)}
      />
    </div>
  );
}

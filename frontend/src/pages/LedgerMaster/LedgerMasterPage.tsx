import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import Badge from '../../components/ui/Badge'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { ledgerService } from '../../services/ledgerService'
import type { LedgerCreatedVia } from '../../types/ledger'

const createLedgerSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  group_id: z.string().min(1, 'Choose a group'),
})

type CreateLedgerForm = z.infer<typeof createLedgerSchema>

const CREATED_VIA_TONE: Record<LedgerCreatedVia, 'gray' | 'blue' | 'green'> = {
  SEED: 'gray',
  RULE: 'gray',
  AI: 'blue',
  MANUAL: 'green',
}

export default function LedgerMasterPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 250)
  const [formError, setFormError] = useState<string | null>(null)

  const { data: ledgers, isLoading } = useQuery({
    queryKey: ['ledgers', debouncedSearch],
    queryFn: () => ledgerService.list(debouncedSearch || undefined),
  })

  const { data: groups } = useQuery({
    queryKey: ['groups'],
    queryFn: () => ledgerService.listGroups(),
    staleTime: 60_000,
  })

  const groupNameById = new Map((groups ?? []).map((g) => [g.id, g.name]))

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateLedgerForm>({ resolver: zodResolver(createLedgerSchema) })

  const createMutation = useMutation({
    mutationFn: (values: CreateLedgerForm) => ledgerService.create(values.name, values.group_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ledgers'] })
      reset()
      setFormError(null)
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Could not create this ledger.'
      setFormError(message)
    },
  })

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Ledger Master</h1>
        <Link to="/dashboard" className="text-sm underline">
          Back to dashboard
        </Link>
      </div>

      <form
        onSubmit={handleSubmit((values) => createMutation.mutate(values))}
        className="mt-6 flex flex-wrap items-end gap-3 rounded border p-4"
        noValidate
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="name" className="text-sm font-medium">
            Ledger name
          </label>
          <input id="name" className="rounded border px-2 py-1 text-sm" {...register('name')} />
          {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="group_id" className="text-sm font-medium">
            Group
          </label>
          <select id="group_id" className="rounded border px-2 py-1 text-sm" {...register('group_id')}>
            <option value="">Select a group…</option>
            {groups?.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
          {errors.group_id && <p className="text-xs text-red-600">{errors.group_id.message}</p>}
        </div>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-slate-900 px-4 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Add ledger
        </button>
        {formError && <p className="w-full text-sm text-red-600">{formError}</p>}
      </form>

      <input
        type="text"
        placeholder="Search ledgers…"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="mt-6 w-full max-w-sm rounded border px-3 py-2 text-sm"
      />

      <div className="mt-4 overflow-x-auto rounded border">
        <table className="min-w-full divide-y text-sm">
          <thead className="bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Group</th>
              <th className="px-3 py-2 text-right">Used</th>
              <th className="px-3 py-2">Created via</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {ledgers?.map((ledger) => (
              <tr key={ledger.id}>
                <td className="px-3 py-2 font-medium">{ledger.name}</td>
                <td className="px-3 py-2 text-gray-500">{groupNameById.get(ledger.group_id) ?? '—'}</td>
                <td className="px-3 py-2 text-right tabular-nums">{ledger.usage_count}</td>
                <td className="px-3 py-2">
                  <Badge tone={CREATED_VIA_TONE[ledger.created_via]}>{ledger.created_via}</Badge>
                </td>
              </tr>
            ))}
            {!isLoading && ledgers?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-gray-400">
                  No ledgers match this search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

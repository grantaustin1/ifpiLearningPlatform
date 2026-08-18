import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface UsePaginatedQueryOptions<T> {
  queryKey: string[]
  url: string
  pageSize?: number
  enabled?: boolean
}

/**
 * Generic paginated query hook built on @tanstack/react-query.
 *
 * Usage:
 *   const { data, page, setPage, isLoading } = usePaginatedQuery<Course>({
 *     queryKey: ['courses'],
 *     url: '/api/courses',
 *     pageSize: 20,
 *   });
 */
export function usePaginatedQuery<T>({
  queryKey,
  url,
  pageSize = 20,
  enabled = true,
}: UsePaginatedQueryOptions<T>) {
  const [page, setPage] = useState(1)

  const { data, isLoading, isFetching, error } = useQuery<PaginatedResponse<T>>({
    queryKey: [...queryKey, page, pageSize],
    queryFn: async () => {
      const { data } = await axios.get(url, {
        params: { page, page_size: pageSize },
      })
      return data
    },
    enabled,
    placeholderData: (previousData) => previousData,
  })

  return {
    data: data?.items ?? [],
    meta: data,
    page,
    setPage,
    pageSize,
    isLoading,
    isFetching,
    error,
  }
}

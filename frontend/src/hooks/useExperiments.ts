import { useQuery } from "@tanstack/react-query";
import {
  activeExperimentsRefetchInterval,
  EXPERIMENTS_QUERY_KEY,
  getExperiments,
} from "../api/experiments";

export function useExperiments() {
  return useQuery({
    queryKey: EXPERIMENTS_QUERY_KEY,
    queryFn: getExperiments,
    refetchInterval: (query) =>
      activeExperimentsRefetchInterval(query.state.data?.items),
  });
}

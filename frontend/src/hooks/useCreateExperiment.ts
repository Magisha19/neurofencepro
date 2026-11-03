import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createExperiment, EXPERIMENTS_QUERY_KEY } from "../api/experiments";

export function useCreateExperiment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createExperiment,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY }),
  });
}

aim to collect around 1000 medical guideline and generate 1000 experience, first start with 100, and those 100 should have the model originally failed

goal 1: 
find 100 cases that llm failed
1. categorize, which case can find medical guideline, which cannot 
2. find similar patient in medqa and mimic, (think about mimic)

rubric need from doctor: 
1. current model diagnosis failure: pick some representative trajectory for doctor to annotate the issue that current llm failed, and provide the general strategy to diagnose different disease
2. similar patient generatation design critic, and building guideline
3. medical guideline generation design critic, and building guideline


## tasks for ai agent

medical guideline disease number analysis
given two medical guidelines
1. experiments/guideline_based_experience/mayoclinical.json (mayoclinical)
2. experiments/guideline_based_experience/结果 (uptodate)

I need stats of unqiue disease that has guideline in either of the two source, so I want a csv file that has column of disease name, and whether it has guideline in mayoclinical or uptodate or both
write the script and csv in experiments/guideline_based_experience

benchmark specific disease' guideline finding 
1. given benchmarks/AgentClinic/agentclinic_medqa_extended_fixed.jsonl, and benchmarks/AgentClinic/agentclinic_mimiciv.jsonl, list the unique disease and whether those disease can be found in medical guideline experiments/guideline_based_experience/mayoclinical.json and txt file in experiments/guideline_based_experience/结果
write the script and csv in experiments/guideline_based_experience

1. first check what disease's guideline are available on 

## goal for human 
the goal of the agent and experience, is given a situation the agent know what need to do next, ask question or do a test 
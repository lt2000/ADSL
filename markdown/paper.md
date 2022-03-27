# Jiffy: Elastic Far-Memory for Stateful Serverless Analytics   Eurosys'22

## Abstract

* Stateful serverless analytics can be enabled **using a remote memory system for inter-task communication, and for storing and exchanging intermediate data**  
* ==However, existing systems **allocate memory resources at job granularity**. **This leads to resource underutilization and/or performance degradation when intermediate data sizes vary during job execution**==

## Introduction

* While originally deemed useful only for **web microservices, IoT and ETL workloads [4, 5]**, recent work on serverless analytics has demonstrated the benefits of serverless architectures for **resource- and cost-efficient data analytics** [6–22]  
* The core idea in serverless analytics is to use a remote low-latency, high-throughput shared far-memory system for: (1) **inter-task communication**; and (2) for **multi-stage jobs**  ,storing intermediate data beyond the lifetime of the task that produced the data (until it is consumed by downstream tasks)  
* We use **far-memory** to refer to memory on remote servers accessed over the network [23, 24], including disaggregated memory [25–40]  
* Such far-memory systems thus allow **decoupling storage, communication and lifetime management of intermediate data from individual compute tasks, enabling serverless analytics frameworks to exploit the on-demand compute elasticity offered by serverless architectures**  
* The problem of performance degradation and resource underutilization for such job-level resource allocation is well understood  

  * if jobs specify their average demand, their performance degrades when instantaneous demand is higher than their average demand
  * if jobs specify their peak demand, the system suffers from resource underutilization when their instantaneous demand is lower than the peak demand  
  * ==As a result, job-level memory allocation in existing systems can lead to significant performance degradation and resource underutilization — over 4.1× performance degradation and 60% resource underutilization in our evaluation==  

* Enabling fine-grained resource allocation requires resolving four unique challenges introduced by serverless analytics
  * performing fine-grained resource allocation requires an efficient mechanism to keep an up-to-date mapping between tasks and memory blocks allocated to individual tasks
  * the number of tasks reading and writing to the shared far-memory system can change rapidly in serverless analytics. Thus, task-level isolation becomes critical: arrival and departure of new tasks should not impact the performance of existing tasks
  * decoupling of serverless tasks from their intermediate data means that the tasks can fail independent of the intermediate data. Thus, we need mechanisms for explicit lifetime management of intermediate data
  * decoupling of tasks from their intermediate data also means that data partitioning upon elastic scaling of memory capacity becomes challenging, especially for certain data types used in serveless analytics

## Motivation

Pocket already resolves a number of interesting challenges pertinent to stateful serverless analytics  

* Scalable centralized management  
* Multi-tiered data storage  
* Adding/removing memory servers  
* Analytics execution with Pocket  

we focus on the specific problems arising out of Pocket’s resource allocation mechanisms

* The core challenge in Pocket’s resource allocation is that it allocates memory at the granularity of jobs  
  * First, accurately predicting intermediate data sizes is hard for many analytics jobs ；a job’s intermediate data size depends on its execution plan, which,in turn, can be adapted dynamically by a query planner  
  * Pocket’s resource allocation mechanism requires jobs to specify their demands at the time of the submission  

## Design

* ==Multiplexing available memory capacity is different from scaling the capacity of the memory pool==  
* 以任务为粒度实现更细粒度的资源分配，以此提高资源利用率

### Hierarchical Addressing  

* Jiffy’s hierarchical addressing — a simple, effective, mechanism that enables Jiffy to maintain a mapping between individual tasks and memory blocks allocated to these tasks, as well as provide isolation at individual task granularity

### Data Lifetime Management  

### Flexible Data Repartitioning  

# Wukong: A Scalable and Locality-Enhanced Framework for Serverless Parallel Computing   SoCC'20

* 分布式调度，一个executor执行DAG中强相关的子图，并提供数据局部性

## Abstract

* Executing complex, burst-parallel, directed acyclic graph (DAG) jobs poses a major challenge for serverless execution frameworks, which will need to **rapidly scale and schedule tasks at high throughput, while minimizing data movement across tasks**  
* **decentralized scheduling** enables scheduling to be distributed across Lambda executors that can schedule tasks in parallel, and brings multiple benefits, including enhanced data locality, reduced network I/Os, automatic resource elasticity, and improved cost effectiveness  

## Introduction

* The scheduler traditionally has various objectives, including load balancing, maximizing cluster utilization, ensuring task fairness, and so on  


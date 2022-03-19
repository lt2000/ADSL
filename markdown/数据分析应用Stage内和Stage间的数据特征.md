# 数据分析应用Stage内和Stage间的数据特征

# 典型的数据分析应用

|                 | Mapreduce sort/Cloudsort benchmark | TPC-DS | Big data benchmark | video analytics | Distributed compilation | ML   |
| :-------------: | :--------------------------------: | :----: | :----------------: | :-------------: | :---------------------: | ---- |
|  Locus NSDI'19  |                 ✔️                  |   ✔️    |         ✔️          |                 |                         |      |
|  Sonic ATC'21   |                 ✔️                  |        |                    |        ✔️        |                         | ✔️    |
| Pocket OSDI'18  |                 ✔️                  |        |                    |        ✔️        |            ✔️            |      |
| Caerus  NSDI'21 |                 ✔️                  |   ✔️    |         ✔️          |                 |                         |      |

# 数据分析应用的主要特征

# 数据分析应用的实验复现

## Pywren

* Users submit single-threaded functions to a global scheduler and while submitting the function they can also annotate the runtime dependencies required. Once the scheduler determines where a function is supposed to run, an appropriate container is created for the duration of execution  
* ==While the container maybe reused to improve performance none of the state created by the function will be retained across invocations. Thus, in such a model all the inputs to functions and all output from functions need to be persisted on remote storage and we include client libraries to access both high-throughput and low latency shared storage systems.==
* While the developer has no control of where a stateless function runs (e.g., the developer cannot specify that a stateless function should run on the node storing the function’s input), the benefits of colocating computation and data –a major design goal for prior systems like Hadoop, Spark and Dryad– have diminished  
* However, technology trends [9, 14, 41] indicate that **the gap between network bandwidth and storage I/O bandwidth is narrowing**, and many recently published proposals for rack-scale computers feature disaggregated storage [3, 20] and even disaggregated memory [13]  
* Currently AWS Lambda provides a very restricted containerized runtime with a maximum 300 seconds of execution time, 1.5 GB of RAM, 512 MB of local storage and no root access  

## Caerus: Nimble Task Scheduling for Serverless Analytics  

## Pocket: Elastic Ephemeral Storage for Serverless Analytics  

### Introduction

* Serverless computing is becoming an increasingly popular cloud service due to its **high elasticity and fine-grain**
  **billing.**  
* Serverless platforms like AWS Lambda, Google Cloud Functions, and Azure Functions **enable users to quickly launch thousands of light-weight tasks**, as opposed to entire virtual machines  
* While serverless platforms were **originally developed for web microservices and IoT applications**, their **elasticity and billing advantages make them appealing for data intensive applications such as interactive analytics**  
* In contrast to traditional serverless applications that consist of a single function executed when a new request arrives, **analytics jobs typically consist of multiple stages and require sharing of state and data across stages of tasks**   
* However, in serverless deployments, **there is no long-running application framework agent to manage local storage**. Furthermore, s**erverless applications have no control over task scheduling or placement, making direct communication among tasks difficult**. As a result of these limitations, the natural approach for **data sharing in serverless applications is to use a remote storage service**  
* Pocket offers high throughput and low latency for arbitrary size data sets, automatic resource scaling, and intelligent data placement across multiple storage tiers such as **DRAM, Flash, and disk**  

### Ephemeral Storage Requirements  

* ==High performance for a wide range of object sizes==  
  * Serverless analytics applications vary considerably in the way they store, distribute, and process data  
  * The key observation is that ephemeral data access granularity varies greatly in size, ranging from hundreds of bytes to hundreds of megabytes  
  * ==an ephemeral data store must deliver high bandwidth, low latency, and high IOPS for the entire range of object sizes==
  * <img src="C:\Users\taoli\AppData\Roaming\Typora\typora-user-images\image-20220314155931707.png" alt="image-20220314155931707" style="zoom:67%;" />
* Automatic and fine-grain scaling  
  * an ephemeral data store must automatically rightsize resources to satisfy application I/O requirements while minimizing cost  
* Storage technology awareness  
  * Hence, the ephemeral data store must place application data on the right storage technology tier(s) for performance and cost efficiency  
* Fault-(in)tolerance  
  - Hence, we argue that an ephemeral storage solution does not have to provide high fault-tolerance as expected of traditional storage systems  
  - <img src="C:\Users\taoli\AppData\Roaming\Typora\typora-user-images\image-20220314155943094.png" alt="image-20220314155943094" style="zoom:67%;" />

### Existing Systems  

* These systems extend the ‘serverless’ abstraction to storage, charging users only for the capacity and bandwidth they use  
* S3 has high latency overhead (e.g., a 1KB read takes ∼12 ms) and insufficient throughput for highly parallel applications  
* Redis and Memcached,offer low latency and high throughput but at the higher cost of DRAM  
* ==Although Amazon and Azure offer managed Redis clusters through their ElastiCache and Redis Cache services respectively, they do not automate storage management as desired by serverless applications== ，Users must still select instance types with the appropriate memory, compute and network resources to match their application requirements  

### Pocket Design  

* Separation of responsibilities: Pocket divides responsibilities across three different planes: the control plane, the metadata plane, and the data plane.
  The control plane manages cluster sizing and data placement. The metadata plane tracks the data stored across nodes in the data plane  
* Sub-second response time  
* Multi-tier storage: Pocket leverages different storage media (DRAM, Flash, disk) to store a job’s data in the tier(s) that satisfy the I/O demands of the application while minimizing cost  
* <img src="C:\Users\taoli\AppData\Roaming\Typora\typora-user-images\image-20220314161827703.png" alt="image-20220314161827703" style="zoom:80%;" />

### Implementation  

* <img src="C:\Users\taoli\AppData\Roaming\Typora\typora-user-images\image-20220314162102391.png" alt="image-20220314162102391" style="zoom:67%;" />

### Evaluation  

##  Understanding Ephemeral Storage for Serverless Analytics  
### Serverless Analytics I/O Properties  

* We study three different serverless analytics applications and characterize their throughput and capacity requirements, data access frequency and I/O size  


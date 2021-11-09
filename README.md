# Securing AWS WorkSpaces with Cisco Secure Workload

## High-level Use Case
VDI is becoming a more popular way to implement remote access solutions for workers, and cloud-based Virtual Desktops offer unique advantages in terms of their ability to scale dynamically and on-demand.  For any VDI environment, the ability to implement consistent security is critical.  This includes consistent visiblity into user behavior, and enhanced control around network access.  Cisco Secure Workload provides:
* Visibility, alerting, and forensics agains all network transactions across all virtual desktops independent of where they live
* Allows for granular and dynamic network access control with it's distributed MultiCloud firewall
* Provides dynamic network quarantining based on workspace posture
* Provides visibility, alerting, and forensic into suspicious process behavior including malicious Tactics, Techniques and Procedures (TTPs) and known malicious process hashes
* Provides visibility into softare inventory and vulnerability

While these capabilities often support security across all datacenter and cloud workloads, there are some unique considerations when deploying Cisco Secure Workload in VDI.  Such as:
1.	Installing Agents in a Golden Image: When leveraging Cisco Tetation in a VDI environment, the agent must be installed in a golden image.  Agents must follow specific configuration best practices to support cloning, and may require additional scheduled tasks due to behaviors like frequent hibernation.
2.	Automatically Adding VDI Instances to the Appropriate Policy Groups: This can be accomplished by getting appropriate context such as "tags and pools" that can then have policy immediately applied.
3.	Cleaning Up Stale Agent Records for Non-Persistent VDI: VDI machines are often transient.  Cisco Secure Workload maintains records of prior installations in case a machine is powered off and may be powered on at a later time.  For VDI agent records must cleaned up when a workspace is active or re-provisioned.

Code from this respository is designed to syncronize AWS WorkSpace context and tags to solve (#2), and automatically clean agent records when a WorkSpace is terminated (#3).  By running these functions in AWS Lambda, Cisco Secure Workload can provide highly automated security for Amazon WorkSpaces.


## Lamda Functions
There are 2 Lambda Functions
1. `annotations_lambda/handler.py` - This syncronizes AWS tags and context (including UserName) with Cisco Secure Workload.
2. `cleanup_lambda/handler.py` - This cleans up Cisco Secure Workload records when a WorkSpace is terminated.


## Environment Variables
No code modification should be required.  The following environment variables need to be provisioned to run the lambda function.

* `ADD_TAGS` -- Applicable only for "annotations_lambda".  Set to 'true' if you want tags attached to WorkSpaces to sync as Annotations in Cisco Secure Workload.  This can increase the time it takes the Lambda to run especially if there are a lot of workspaces.  Can be left blank.
* `ATTRIBUTES_LIST` -- Required.  These are additional fields to sync as Cisco Secure Workload annotations.  Comma separated format.  Recommended value is "UserName"
* `DELETE_SENSORS` -- Applicable only for "cleanup_lambda".  Set to 'true' if you want sensor records to be removed when a WorkSpace is terminated (recommended).
* `TET_URL` -- Cisco Secure Workload URL
* `TET_API_KEY` -- Cisco Secure Workload API key with User data upload and sensor management capabilities.
* `TET_API_SECRET` -- Cisco Secure Workload API secret with User data upload and sensor management capabilities.
* `TET_TENANT` -- Cisco Secure Workload Root Scope/Tenant name.
* `AWS_REGION` -- Example "us-east-1"


## Preparing a package and deploying to Lambda
The scripts are optimized for Python3.  It will also require additional dependent packages.  To build a package that can then be uploaded to lambda you will need to:
1. Clone the git repository
2. Move to the directory for one of the lambda's.  i.e.
```bash
cd tetration-aws-workspaces
cd annotations_lambda
```
3. Install tetpyclient and it's dependencies locally in that folder by typing `pip3 install tetpyclient -t .`.  This will download all of the additional python dependency code required.  Boto3 is included in the AWS Lambda runtime, so it does not need to be installed locally unless the function is being tested locally.
4. Zip the entire annotations_lambda folder.
5. Create a Lambda function in the AWS console with the Python 3.x runtime
6. Upload the ZIP file to the Lambda
7. Create a recurring event to run the Lambda for syncronization leveraging CloudWatch events.  This is essentially like a cron job.  For the annotations_lambda, it's recommended that it repeats every 2 minutes.  For the cleanup_lambda, every 10 minutes is sufficent.
8. Ensure that the lambda function is running with a role that read-only access to Amazon WorkSpaces API.
9. Ensure that the Environment Variables are set properly in the Lambda configuration.
10. Ensure that the lambda execution duration is sufficient.  If syncronizing tags, 30 seconds may be required especially for larger numbers of workspaces.  If not syncronizing tags, execution should be under 10 second.
11. Repeat for the other lambda function.

Final configuration for the Lambda should look like this:

-- Insert Picture Here -- 

## Prepping a Golden Image
There are three things that need to be done to prep a golden image for cloning with the Cisco Secure Workload agent in-place:
* Install the Cisco Secure Workload Agent
* Anonymize the Cisco Secure Workload Agent
* Create a Scheduled Task to Optimize the Agent for Image Hibernation

### Installing the Cisco Secure Workload Agent
The agent can be installed as normal.  It is recommended to leverage the PowerShell "Easy Installer".

### Anonymizing the Cisco Secure Workload Agent for Cloning
Each agent installation has a unique certificate and UUID that is generated on install.  If a golden image were cloned, and passes on its UUID, the clone will fail to register.  Thus, when preparing the image, you must anonymize the install before converting it to a template.
1. Stop the Cisco Secure Workload Agent Services.  In 3.3 those services are "WinTetEngine" and "WinAgentEngine". Occasionally the sysprep process when an image is being converted to a template could re-generated the UUID.  Thus, inaddition to stopping the services, it is recommended to set the service to "Delayed Start".
2. Delete The UUID and Certificate Files.  With the default install path, those files are:
```
C:\Program Files\Cisco Tetration\sensor_uuid
C:\Program Files\Cisco Tetration\cert\client.cert
C:\Program Files\Cisco Tetration\cert\client.key
```
### Accomidating Image Hibernation
It's very common in AWS WorkSpaces for an image to go into hibernation.  In order to ensure that the latest policy is applied immediatly when the image resumes, a scheduled task should be created to re-start the agent service and reset the connection as soon as the image wakes up.  The following files provide examples:

* `workspace_scheduled_task/RestartTetrationOnResume.xml` - This is a template for a scheduled task.  Note the following...
    * The task is scheduled to run as the NT AUTHORITY/SYSTEM user with "Highest Available" priviledges to ensure that it can restart services.
    * The trigger is against a event log "System" -> "WindowsPowerTroubleshooter" -> "Event ID = 1".  This event occurs anytime the system wakes from sleep.
    * The action is to leverage powershell.exe to run a powershell script.  This is executed with the following flags so that it is invisibile to the user: `-NoLogo -NonInteractive -WindowStyle Hidden -File "C:\start_enforcement_agent.ps1"`
* `workspace_scheduled_task/start_enforcement_agent.ps1` - This is the powershell script that is executed.  Note that it loops checking connectivity to "www.tetrationcloud.com" before restarting the services.  For an on-premises deployment, this should be changed to one of the pingable Cisco Secure Workload cluster IP addresses.  The services in the restart script are "WinTetEngine" and "WinAgentEngine".  These are the service names as of Cisco Secure Workload version 3.3, but service names are subject to change with future releases.
use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use justverify::{Rpc, Snapshot, clean, probe_electrs, probe_tor};
use serde_json::json;
use std::{
    fs,
    io::{Read, Write},
    os::unix::{
        fs::PermissionsExt,
        net::{UnixListener, UnixStream},
    },
    path::PathBuf,
    sync::{Arc, RwLock},
    thread,
    time::Duration,
};

#[derive(Parser)]
#[command(version, about = "JustVerify personal Bitcoin node")]
struct Args {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    ValidatePolicy {
        #[arg(long)]
        catalog: PathBuf,
        #[arg(long)]
        version: String,
        #[arg(long)]
        network: String,
        #[arg(long)]
        config: PathBuf,
    },
    VersionService {
        #[arg(long)]
        config: PathBuf,
        #[arg(long)]
        socket: PathBuf,
    },
    PolicyService {
        #[arg(long)]
        profile: PathBuf,
        #[arg(long)]
        socket: PathBuf,
    },
    PrepareInstance {
        #[arg(long)]
        root: PathBuf,
        #[arg(long)]
        version: String,
        #[arg(long, default_value = "regtest")]
        network: String,
        #[arg(long, default_value = "0.11.1")]
        electrs: String,
    },
    Daemon {
        #[arg(long)]
        cookie: PathBuf,
        #[arg(long, default_value_t = 18443)]
        rpc_port: u16,
        #[arg(long, default_value_t = 50001)]
        electrs_port: u16,
        #[arg(long, default_value_t = 9050)]
        tor_port: u16,
        #[arg(long)]
        socket: PathBuf,
    },
    Tui {
        #[arg(long)]
        socket: PathBuf,
        #[arg(long)]
        no_color: bool,
        #[arg(long, default_value = "/run/justverify-policy/control.sock")]
        policy_socket: PathBuf,
    },
    Snapshot {
        #[arg(long)]
        socket: PathBuf,
    },
}
fn get(socket: &PathBuf) -> Result<Snapshot> {
    let mut stream = UnixStream::connect(socket).context("management daemon unavailable")?;
    stream.set_read_timeout(Some(Duration::from_secs(4)))?;
    stream.write_all(b"snapshot\n")?;
    let mut bytes = Vec::new();
    stream.take(2 * 1024 * 1024).read_to_end(&mut bytes)?;
    Ok(serde_json::from_slice(&bytes)?)
}
fn main() -> Result<()> {
    match Args::parse().command {
        Command::ValidatePolicy {
            catalog,
            version,
            network,
            config,
        } => {
            let policy = justverify::policy::Policy::load(&catalog, &version, &network)?;
            policy.current(&config)?;
            println!("VALID");
        }
        Command::VersionService { config, socket } => {
            justverify::version_service::serve(&config, &socket)?
        }
        Command::PolicyService { profile, socket } => {
            justverify::policy_service::serve(&profile, &socket)?
        }
        Command::PrepareInstance {
            root,
            version,
            network,
            electrs,
        } => {
            let target = justverify::storage::instance(&root, &version, &network, &electrs)?;
            justverify::storage::prepare(&target)?;
            println!("{}", serde_json::to_string_pretty(&target)?);
        }
        Command::Daemon {
            cookie,
            rpc_port,
            electrs_port,
            tor_port,
            socket,
        } => {
            if socket.exists() {
                bail!("socket already exists; confirm old daemon is stopped before removing it");
            }
            let parent = socket.parent().context("socket directory required")?;
            fs::create_dir_all(parent)?;
            let mode = fs::metadata(parent)?.permissions().mode();
            if mode & 0o077 != 0 {
                bail!("socket directory must be private (chmod 700)");
            }
            let listener = UnixListener::bind(&socket)?;
            fs::set_permissions(&socket, fs::Permissions::from_mode(0o600))?;
            let cache = Arc::new(RwLock::new(Snapshot::default()));
            let writer = cache.clone();
            let rpc = Rpc::new(rpc_port, &cookie)?;
            thread::spawn(move || {
                let mut state = Snapshot::default();
                let mut host = sysinfo::System::new_all();
                let mut disks = sysinfo::Disks::new_with_refreshed_list();
                let mut last_disk_refresh = 0;
                loop {
                    rpc.collect(&mut state);
                    host.refresh_memory();
                    host.refresh_cpu_usage();
                    state.host = json!({"hostname":clean(&sysinfo::System::host_name().unwrap_or_default()),"uptime":sysinfo::System::uptime(),"used_memory_mib":host.used_memory()/1048576,"total_memory_mib":host.total_memory()/1048576,"cpu_percent":format!("{:.1}",host.global_cpu_usage())});
                    if justverify::now().saturating_sub(last_disk_refresh) >= 10 {
                        disks.refresh(true);
                        last_disk_refresh = justverify::now();
                    }
                    state.host["disks"]=json!(disks.iter().map(|d|json!({"mount":clean(&d.mount_point().display().to_string()),"total":d.total_space(),"available":d.available_space()})).collect::<Vec<_>>());
                    state.host["swap_mib"] = json!(host.used_swap() / 1048576);
                    state.host["electrs"] = probe_electrs(electrs_port, &state);
                    state.host["tor"] = probe_tor(tor_port);
                    *writer.write().unwrap() = state.clone();
                    thread::sleep(Duration::from_secs(2));
                }
            });
            for stream in listener.incoming() {
                let mut stream = stream?;
                stream.set_read_timeout(Some(Duration::from_secs(1)))?;
                stream.set_write_timeout(Some(Duration::from_secs(1)))?;
                let mut request = [0; 9];
                if stream.read_exact(&mut request).is_ok() && &request == b"snapshot\n" {
                    let payload = serde_json::to_vec(&*cache.read().unwrap())?;
                    let _ = stream.write_all(&payload);
                }
            }
        }
        Command::Snapshot { socket } => {
            println!("{}", serde_json::to_string_pretty(&get(&socket)?)?)
        }
        Command::Tui {
            socket,
            policy_socket,
            no_color,
        } => justverify::tui::run(&socket, &policy_socket, no_color)?,
    }
    Ok(())
}

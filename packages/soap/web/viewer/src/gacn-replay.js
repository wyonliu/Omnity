/**
 * GenerativeAgentsCN 回放 Phaser 逻辑 1:1 自
 * generative_agents/frontend/templates/main_script.html（路径改为 /vendor/generative-agents-cn/assets/village/…）
 */
import Phaser from "phaser";

const TILE_WIDTH = 32;

function slugAgentPath(name) {
  return String(name).replace(/ /g, "_");
}

function injectPersonaDomAnchors(personaInitPos) {
  const root = document.getElementById("gacn-hidden-anchors");
  if (!root) return;
  root.innerHTML = "";
  for (const name of Object.keys(personaInitPos || {})) {
    const esc = (s) =>
      String(s)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;");
    const id = esc(name);
    root.insertAdjacentHTML(
      "beforeend",
      `<div id="agent_desc__${id}"></div><div id="current_action__${id}"></div><div id="target_address__${id}"></div>`,
    );
  }
}

/**
 * @param {string} parentId
 * @param {object} boot 对齐 Flask 注入字段
 * @returns {{ destroy: () => void, game: Phaser.Game }}
 */
export function mountGacnFullReplay(parentId, boot) {
  injectPersonaDomAnchors(boot.persona_init_pos);

  const BASE = "/vendor/generative-agents-cn/assets/village";
  let step = boot.step ?? 1;
  const step_size = (boot.sec_per_step ?? 10) * 1000;
  let zoom = boot.zoom > 0 ? boot.zoom : document.documentElement.clientWidth / 4400;
  const movement_speed = boot.play_speed ?? 4;
  let execute_count_max = TILE_WIDTH / Math.max(0.001, movement_speed);
  let execute_count = execute_count_max;
  const all_movement = boot.all_movement || {};
  const datetime_options = {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  };
  let start_datetime = new Date(Date.parse(boot.start_datetime));

  const persona_names = boot.persona_init_pos || {};
  const spawn_tile_loc = { ...persona_names };
  const personas = {};
  const pronunciatios = {};
  let anims_direction;
  let pre_anims_direction;
  const pre_anims_direction_dict = {};
  const movement_target = {};
  let finished = false;
  let paused = false;

  let cursors;
  let player;
  let buttonPlay;
  let buttonPause;
  let buttonShowConversation;
  let buttonHideConversation;
  let currentTime;
  let textConversation;

  let gameRef;

  function add_text(scene, x, y, text, background) {
    const res = scene.add.text(x, y, text, {
      font: "24px 黑体",
      fontWeight: "normal",
      fill: "#000000",
      backgroundColor: background,
      padding: { x: 20, y: 4 },
      align: "left",
      wordWrap: { width: 1200 / zoom, useAdvancedWrap: true },
    });
    res.setDepth(10);
    res.alpha = 0.8;
    res.setScrollFactor(0);
    return res;
  }

  function preload() {
    this.load.crossOrigin = "";

    this.load.image("blocks_1", `${BASE}/tilemap/blocks_1.png`);
    this.load.image("walls", `${BASE}/tilemap/Room_Builder_32x32.png`);
    this.load.image("interiors_pt1", `${BASE}/tilemap/interiors_pt1.png`);
    this.load.image("interiors_pt2", `${BASE}/tilemap/interiors_pt2.png`);
    this.load.image("interiors_pt3", `${BASE}/tilemap/interiors_pt3.png`);
    this.load.image("interiors_pt4", `${BASE}/tilemap/interiors_pt4.png`);
    this.load.image("interiors_pt5", `${BASE}/tilemap/interiors_pt5.png`);
    this.load.image("CuteRPG_Field_B", `${BASE}/tilemap/CuteRPG_Field_B.png`);
    this.load.image("CuteRPG_Field_C", `${BASE}/tilemap/CuteRPG_Field_C.png`);
    this.load.image("CuteRPG_Harbor_C", `${BASE}/tilemap/CuteRPG_Harbor_C.png`);
    this.load.image("CuteRPG_Village_B", `${BASE}/tilemap/CuteRPG_Village_B.png`);
    this.load.image("CuteRPG_Forest_B", `${BASE}/tilemap/CuteRPG_Forest_B.png`);
    this.load.image("CuteRPG_Desert_C", `${BASE}/tilemap/CuteRPG_Desert_C.png`);
    this.load.image("CuteRPG_Mountains_B", `${BASE}/tilemap/CuteRPG_Mountains_B.png`);
    this.load.image("CuteRPG_Desert_B", `${BASE}/tilemap/CuteRPG_Desert_B.png`);
    this.load.image("CuteRPG_Forest_C", `${BASE}/tilemap/CuteRPG_Forest_C.png`);

    this.load.tilemapTiledJSON("map", `${BASE}/tilemap/tilemap.json`);

    this.load.atlas(
      "atlas",
      `${BASE}/agents/伊莎贝拉/texture.png`,
      `${BASE}/agents/sprite.json`,
    );

    for (const p in persona_names) {
      if (!Object.prototype.hasOwnProperty.call(persona_names, p)) continue;
      const path = `${BASE}/agents/${slugAgentPath(p)}/texture.png`;
      this.load.atlas(p, path, `${BASE}/agents/sprite.json`);
    }
  }

  function create() {
    const map = this.make.tilemap({ key: "map" });

    const collisions = map.addTilesetImage("blocks", "blocks_1");
    const wallsTs = map.addTilesetImage("Room_Builder_32x32", "walls");
    const interiors_pt1 = map.addTilesetImage("interiors_pt1", "interiors_pt1");
    const interiors_pt2 = map.addTilesetImage("interiors_pt2", "interiors_pt2");
    const interiors_pt3 = map.addTilesetImage("interiors_pt3", "interiors_pt3");
    const interiors_pt4 = map.addTilesetImage("interiors_pt4", "interiors_pt4");
    const interiors_pt5 = map.addTilesetImage("interiors_pt5", "interiors_pt5");
    const CuteRPG_Field_B = map.addTilesetImage("CuteRPG_Field_B", "CuteRPG_Field_B");
    const CuteRPG_Field_C = map.addTilesetImage("CuteRPG_Field_C", "CuteRPG_Field_C");
    const CuteRPG_Harbor_C = map.addTilesetImage("CuteRPG_Harbor_C", "CuteRPG_Harbor_C");
    const CuteRPG_Village_B = map.addTilesetImage("CuteRPG_Village_B", "CuteRPG_Village_B");
    const CuteRPG_Forest_B = map.addTilesetImage("CuteRPG_Forest_B", "CuteRPG_Forest_B");
    const CuteRPG_Desert_C = map.addTilesetImage("CuteRPG_Desert_C", "CuteRPG_Desert_C");
    const CuteRPG_Mountains_B = map.addTilesetImage("CuteRPG_Mountains_B", "CuteRPG_Mountains_B");
    const CuteRPG_Desert_B = map.addTilesetImage("CuteRPG_Desert_B", "CuteRPG_Desert_B");
    const CuteRPG_Forest_C = map.addTilesetImage("CuteRPG_Forest_C", "CuteRPG_Forest_C");

    const tileset_group_1 = [
      CuteRPG_Field_B,
      CuteRPG_Field_C,
      CuteRPG_Harbor_C,
      CuteRPG_Village_B,
      CuteRPG_Forest_B,
      CuteRPG_Desert_C,
      CuteRPG_Mountains_B,
      CuteRPG_Desert_B,
      CuteRPG_Forest_C,
      interiors_pt1,
      interiors_pt2,
      interiors_pt3,
      interiors_pt4,
      interiors_pt5,
      wallsTs,
    ].filter(Boolean);

    map.createLayer("Bottom Ground", tileset_group_1, 0, 0);
    map.createLayer("Exterior Ground", tileset_group_1, 0, 0);
    map.createLayer("Exterior Decoration L1", tileset_group_1, 0, 0);
    map.createLayer("Exterior Decoration L2", tileset_group_1, 0, 0);
    map.createLayer("Interior Ground", tileset_group_1, 0, 0);
    map.createLayer("Wall", [CuteRPG_Field_C, wallsTs].filter(Boolean), 0, 0);
    map.createLayer("Interior Furniture L1", tileset_group_1, 0, 0);
    map.createLayer("Interior Furniture L2 ", tileset_group_1, 0, 0);
    const foregroundL1Layer = map.createLayer("Foreground L1", tileset_group_1, 0, 0);
    const foregroundL2Layer = map.createLayer("Foreground L2", tileset_group_1, 0, 0);

    const collisionsLayer = collisions ? map.createLayer("Collisions", collisions, 0, 0) : null;
    if (collisionsLayer) {
      collisionsLayer.setCollisionByProperty({ collide: true });
      collisionsLayer.setDepth(-1);
    }
    if (foregroundL1Layer) foregroundL1Layer.setDepth(2);
    if (foregroundL2Layer) foregroundL2Layer.setDepth(2);

    const canvas = this.sys.game.canvas;
    canvas.addEventListener(
      "wheel",
      (event) => {
        event.stopPropagation();
      },
      { passive: false, capture: true },
    );

    let posX = 20;
    let posY = 20;

    buttonPlay = add_text(this, posX, posY, "[运行]", "#ffffcc");
    buttonPlay.setInteractive();
    posX += buttonPlay.width + 10;

    buttonPause = add_text(this, posX, posY, " 暂停 ", "#ffffcc");
    buttonPause.setInteractive();
    posX += buttonPause.width + 10;

    buttonShowConversation = add_text(this, posX, posY, "[显示对话]", "#ffffcc");
    buttonShowConversation.setInteractive();
    posX += buttonShowConversation.width + 10;

    buttonHideConversation = add_text(this, posX, posY, " 隐藏对话 ", "#ffffcc");
    buttonHideConversation.setInteractive();
    posX += buttonHideConversation.width + 10;

    currentTime = add_text(this, posX, posY, "", "#ccffcc");
    textConversation = add_text(this, 20, posY + currentTime.height + 10, " —— ", "#ccffcc");

    player = this.physics.add.sprite(2440, 500, "atlas", "down").setSize(30, 40).setOffset(0, 0);
    player.setDepth(-1);
    const camera = this.cameras.main;
    camera.startFollow(player);
    camera.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
    cursors = this.input.keyboard.addKeys({
      up: Phaser.Input.Keyboard.KeyCodes.UP,
      down: Phaser.Input.Keyboard.KeyCodes.DOWN,
      left: Phaser.Input.Keyboard.KeyCodes.LEFT,
      right: Phaser.Input.Keyboard.KeyCodes.RIGHT,
    });

    const personaKeys = Object.keys(persona_names);
    for (let i = 0; i < personaKeys.length; i++) {
      const persona_name = personaKeys[i];
      const start_pos = spawn_tile_loc[persona_name];
      const curr_persona = this.physics.add.sprite(
        Number(start_pos[0]) * TILE_WIDTH,
        Number(start_pos[1]) * TILE_WIDTH,
        persona_name,
        "down",
      );
      curr_persona.setSize(30, 40).setOffset(0, 0);
      personas[persona_name] = curr_persona;
      const curr_pronunciatio = add_text(
        this,
        Number(start_pos[0]) * TILE_WIDTH,
        Number(start_pos[1]) * TILE_WIDTH,
        `${persona_name}: ⏳`,
        "#ffffff",
      );
      pronunciatios[persona_name] = curr_pronunciatio;
    }

    const anims = this.anims;
    for (let i = 0; i < personaKeys.length; i++) {
      const persona_name = personaKeys[i];
      const left_walk_name = `${persona_name}-left-walk`;
      const right_walk_name = `${persona_name}-right-walk`;
      const down_walk_name = `${persona_name}-down-walk`;
      const up_walk_name = `${persona_name}-up-walk`;
      const frameRate = persona_name.includes("阿伊莎") ? 4 : 8;

      anims.create({
        key: left_walk_name,
        frames: anims.generateFrameNames(persona_name, {
          prefix: "left-walk.",
          start: 0,
          end: 3,
          zeroPad: 3,
        }),
        frameRate,
        repeat: -1,
      });
      anims.create({
        key: right_walk_name,
        frames: anims.generateFrameNames(persona_name, {
          prefix: "right-walk.",
          start: 0,
          end: 3,
          zeroPad: 3,
        }),
        frameRate,
        repeat: -1,
      });
      anims.create({
        key: down_walk_name,
        frames: anims.generateFrameNames(persona_name, {
          prefix: "down-walk.",
          start: 0,
          end: 3,
          zeroPad: 3,
        }),
        frameRate,
        repeat: -1,
      });
      anims.create({
        key: up_walk_name,
        frames: anims.generateFrameNames(persona_name, {
          prefix: "up-walk.",
          start: 0,
          end: 3,
          zeroPad: 3,
        }),
        frameRate,
        repeat: -1,
      });
    }

    buttonPlay.on("pointerdown", function () {
      if (finished) return;
      buttonPlay.setText("[运行]");
      buttonPause.setText(" 暂停 ");
      paused = false;
    });

    buttonPause.on("pointerdown", function () {
      if (finished) return;
      buttonPlay.setText(" 运行 ");
      buttonPause.setText("[暂停]");
      paused = true;
    });

    buttonShowConversation.on("pointerdown", function () {
      buttonShowConversation.setText("[显示对话]");
      buttonHideConversation.setText(" 隐藏对话 ");
      textConversation.setVisible(true);
    });

    buttonHideConversation.on("pointerdown", function () {
      buttonShowConversation.setText(" 显示对话 ");
      buttonHideConversation.setText("[隐藏对话]");
      textConversation.setVisible(false);
    });
  }

  function update() {
    const camera_speed = 400;
    player.body.setVelocity(0);
    if (cursors.left.isDown) player.body.setVelocityX(-camera_speed);
    if (cursors.right.isDown) player.body.setVelocityX(camera_speed);
    if (cursors.up.isDown) player.body.setVelocityY(-camera_speed);
    if (cursors.down.isDown) player.body.setVelocityY(camera_speed);

    const tempFocus = document.getElementById("temp_focus");
    const curr_focused_persona = tempFocus ? tempFocus.textContent : "";
    if (curr_focused_persona !== "" && personas[curr_focused_persona]) {
      player.body.x = personas[curr_focused_persona].body.x;
      player.body.y = personas[curr_focused_persona].body.y;
      tempFocus.innerHTML = "";
    }

    if (finished || paused) {
      return;
    }

    const convRoot = all_movement.conversation || {};
    const descRoot = all_movement.description || {};
    let curr_datetime = new Date(start_datetime.getTime());
    const curr_year = curr_datetime.getFullYear().toString().padStart(4, "0");
    const curr_month = (curr_datetime.getMonth() + 1).toString().padStart(2, "0");
    const curr_day = curr_datetime.getDate().toString().padStart(2, "0");
    const curr_hour = curr_datetime.getHours().toString().padStart(2, "0");
    const curr_minute = curr_datetime.getMinutes().toString().padStart(2, "0");
    const conversation_key = `${curr_year}${curr_month}${curr_day}-${curr_hour}:${curr_minute}`;
    const conversation_key_text = convRoot[conversation_key];
    if (conversation_key_text && conversation_key_text !== "") {
      textConversation.setText(`\n${conversation_key} 对话记录：\n${conversation_key_text}`);
    }

    const stepKey = String(step);
    const stepBlock = all_movement[stepKey];

    for (let i = 0; i < Object.keys(personas).length; i++) {
      const curr_persona_name = Object.keys(personas)[i];
      const curr_persona = personas[curr_persona_name];
      const curr_pronunciatio = pronunciatios[curr_persona_name];
      const movementName = curr_persona_name.replace("_", " ");

      if (stepBlock !== undefined && stepBlock !== null) {
        if (movementName in stepBlock) {
          if (execute_count === execute_count_max) {
            const entry = stepBlock[movementName];
            const curr_x = entry.movement[0];
            const curr_y = entry.movement[1];
            movement_target[curr_persona_name] = [curr_x * TILE_WIDTH, curr_y * TILE_WIDTH];

            let action = entry.action;
            const act = action.length > 25 ? `${action.substring(0, 20)}...` : action;
            curr_pronunciatio.setText(`${curr_persona_name}: ${act}`);

            const descEl = document.getElementById(`agent_desc__${curr_persona_name}`);
            const actEl = document.getElementById(`current_action__${curr_persona_name}`);
            const addrEl = document.getElementById(`target_address__${curr_persona_name}`);
            const d = descRoot[curr_persona_name];
            if (descEl && d) descEl.innerHTML = d.currently ?? "";
            if (actEl) actEl.innerHTML = action;
            if (addrEl) addrEl.innerHTML = entry.location ?? "";
          }

          if (execute_count > 0) {
            const tx = movement_target[curr_persona_name][0];
            const ty = movement_target[curr_persona_name][1];
            if (curr_persona.body.x < tx) {
              curr_persona.body.x += movement_speed;
              anims_direction = "r";
              pre_anims_direction = "r";
              pre_anims_direction_dict[curr_persona_name] = "r";
            } else if (curr_persona.body.x > tx) {
              curr_persona.body.x -= movement_speed;
              anims_direction = "l";
              pre_anims_direction = "l";
              pre_anims_direction_dict[curr_persona_name] = "l";
            } else if (curr_persona.body.y < ty) {
              curr_persona.body.y += movement_speed;
              anims_direction = "d";
              pre_anims_direction = "d";
              pre_anims_direction_dict[curr_persona_name] = "d";
            } else if (curr_persona.body.y > ty) {
              curr_persona.body.y -= movement_speed;
              anims_direction = "u";
              pre_anims_direction = "u";
              pre_anims_direction_dict[curr_persona_name] = "u";
            } else {
              anims_direction = "";
            }

            curr_pronunciatio.x = curr_persona.body.x - 15;
            curr_pronunciatio.y = curr_persona.body.y - 15 - 25;

            const left_walk_name = `${curr_persona_name}-left-walk`;
            const right_walk_name = `${curr_persona_name}-right-walk`;
            const down_walk_name = `${curr_persona_name}-down-walk`;
            const up_walk_name = `${curr_persona_name}-up-walk`;

            if (anims_direction === "l") curr_persona.anims.play(left_walk_name, true);
            else if (anims_direction === "r") curr_persona.anims.play(right_walk_name, true);
            else if (anims_direction === "u") curr_persona.anims.play(up_walk_name, true);
            else if (anims_direction === "d") curr_persona.anims.play(down_walk_name, true);
          }
        }
      } else {
        const pad = pre_anims_direction_dict[curr_persona_name];
        if (pad === "l") curr_persona.setTexture(curr_persona_name, "left");
        else if (pad === "r") curr_persona.setTexture(curr_persona_name, "right");
        else if (pad === "u") curr_persona.setTexture(curr_persona_name, "up");
        else if (pad === "d") curr_persona.setTexture(curr_persona_name, "down");
        curr_persona.anims.stop();

        finished = true;
        buttonPlay.setText("[回放结束]");
        buttonPause.setVisible(false);
      }
    }

    if (execute_count === 0) {
      for (let i = 0; i < Object.keys(personas).length; i++) {
        const curr_persona_name = Object.keys(personas)[i];
        const curr_persona = personas[curr_persona_name];
        if (movement_target[curr_persona_name]) {
          curr_persona.body.x = movement_target[curr_persona_name][0];
          curr_persona.body.y = movement_target[curr_persona_name][1];
        }
      }
      execute_count = execute_count_max + 1;
      step += 1;
      start_datetime = new Date(start_datetime.getTime() + step_size);
      currentTime.setText(start_datetime.toLocaleTimeString("zh-CN", datetime_options));
    }

    execute_count -= 1;
  }

  gameRef = new Phaser.Game({
    type: Phaser.AUTO,
    width: document.documentElement.clientWidth / zoom,
    height: document.documentElement.clientHeight / zoom,
    parent: parentId,
    pixelArt: true,
    physics: {
      default: "arcade",
      arcade: { gravity: { y: 0 } },
    },
    scale: {
      mode: Phaser.Scale.NONE,
      autoCenter: Phaser.Scale.CENTER_BOTH,
      zoom,
    },
    scene: { preload, create, update },
  });

  return {
    destroy: () => {
      gameRef?.destroy(true);
      gameRef = null;
    },
    get game() {
      return gameRef;
    },
  };
}

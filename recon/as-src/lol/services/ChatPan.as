class lol.services.ChatPan extends lol.gpui.GPUIObject
{
   var LastString;
   var PartyButton_Visible;
   var PartyPanel_Visible;
   var XMC;
   var _name;
   var _parent;
   var back;
   var backBottom;
   var channelPan;
   var chat;
   var chatChannelPan;
   var chatInput;
   var chatListPan;
   var chatOutput;
   var chatResize;
   var clanInspector;
   var clanMemberList;
   var contextMenuPlayer;
   var dispatchEvent;
   var erase_btn;
   var globalMap;
   var line_bottom;
   var line_top;
   var listChatBtn;
   var listPanCont_mc;
   var listPrivate;
   var location;
   var main;
   var master;
   var partyList;
   var partyListPan;
   var partyManager;
   var scrBar;
   var send_btn;
   var stackArr;
   var tempID;
   var tempMessArr;
   var tempStr;
   var time_btn;
   var userList;
   static var DEFAULT_H = 144;
   static var MESSAGE_MAX_CHAR = 80;
   var TIME_OUT = 3000;
   var TRADE_TIME_OUT = 3000;
   var chatFocus = false;
   var currentChannel = 0;
   static var call_delay_ = 3000;
   var sendAllow = true;
   var isDrag = false;
   var flag = false;
   function ChatPan()
   {
      super();
      this.userList = this.chatListPan.userList;
      this.userList.listItemLink = "chatItem";
      this.partyList = this.partyListPan.partyList;
      this.partyList.listItemLink = "partyItem";
      lol.events.LEventDispatcher.initialize(this);
      this.master = lol.core.Master.getInstance();
      this.doLater("init");
      this.PartyPanel_Visible = false;
      this.PartyButton_Visible = false;
   }
   function init()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.chat = this.master.chat;
      this.chat.addEventListener("refresh",this);
      this.chatChannelPan = this.channelPan.chatChannelPan;
      this.chatListPan.back_btn.useHandCursor = false;
      this.partyListPan.back_btn.useHandCursor = false;
      this.chatChannelPan.addEventListener("showChannel",this,this.showChannel);
      this.partyListPan.hidePartyPan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showHidePartyPan);
      this.topBtnInit();
      this.userList.setSize(this.userList.mask_mc._width,this.userList.mask_mc._height);
      this.partyList.setSize(this.partyList.mask_mc._width,this.partyList.mask_mc._height);
      this.send_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sendMessage);
      lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.SEND_MESSAGE,this.send_btn);
      this.initUsers();
      this.chatOutput.text = "";
      this.scrBar._visible = false;
      this.scrBar.scrollValue = 2;
      this.scrBar.setSize(104);
      this.scrBar.target = this.chatOutput;
      this.scrBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrollUp);
      this.scrBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrollDown);
      this.scrBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.stopScroll);
      this.scrBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.stopScroll);
      this.chatOutput.onScroller = mx.utils.Delegate.create(this,this.scrollText);
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this);
      this.resizeStage({w:Stage.width,h:Stage.height});
      this.chatResize.onPress = mx.utils.Delegate.create(this,this.startResize);
      this.chatResize.onRelease = mx.utils.Delegate.create(this,this.stopResize);
      this.chatResize.onReleaseOutside = mx.utils.Delegate.create(this,this.stopResizeOut);
      this.chatResize.onRollOver = function()
      {
         this._parent.showCursor(true);
      };
      this.chatResize.onRollOut = function()
      {
         this._parent.showCursor(false);
      };
      this.main = lol.core.SceneShifter.main;
      this.chatInput.onKillFocus = function()
      {
         lol.core.SceneShifter.hotKeyManager.removeFilter("chat");
         lol.core.SceneShifter.hotKeyManager.enabled = true;
         Key.removeListener(this._parent);
      };
      this.chatInput.onSetFocus = function()
      {
         lol.core.SceneShifter.hotKeyManager.addFilter("chat");
         lol.core.SceneShifter.hotKeyManager.enabled = false;
         Key.addListener(this._parent);
      };
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CHAT_IN_FOCUS,this,this.chatActivation);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.RETURN_OLD_NAME,this,this.chatSetLastName);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.ESC,this,this.chatDeactivation);
      this.time_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.timeInMessage);
      this.erase_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.eraseOutput);
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TIME_IN_CHAT);
      this.time_btn.toggled = _loc2_;
      var _loc3_ = new lol.utils.Timeout(this,this.sendFirstMessage,1000);
   }
   function setPrivateToInputStr(withID)
   {
      this.chatInput.text = "private " + this.getName(withID) + ": ";
   }
   function chatActivation()
   {
      this.tempStr = this.chatInput.text;
      this.doLater("loadText");
      this.chatFocus = true;
   }
   function chatDeactivation()
   {
      Selection.setFocus(null);
   }
   function loadText()
   {
      Selection.setFocus(this.chatInput);
      Selection.setSelection(this.tempStr.length,this.tempStr.length);
   }
   function onMouseDown()
   {
      Selection.setFocus(null);
   }
   function chatSetLastName()
   {
      if(this.LastString)
      {
         this.chatInput.text = this.LastString;
         this.doLater("gotoLastSymbol");
      }
   }
   function topBtnInit()
   {
      this.listPrivate = new Array();
      this.listChatBtn = new Array();
      this.chatChannelPan.setSize(this.chatOutput._width + 20);
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_PRIVATE_CHANNEL,undefined);
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_HELP_CHANNEL))
      {
         this.createHelpChannel();
      }
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_WORLD_CHANNEL))
      {
         this.createWorldChannel();
      }
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TRADE_CHANNEL))
      {
         this.createTradeChannel();
      }
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_EVENT_CHANNEL))
      {
         this.createEventChannel();
      }
      this.doLater("initChannel",[lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined]);
      this.doLater("checkClan");
      this.doLater("checkParty");
   }
   function createTradeChannel()
   {
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_TRADE_CHANNEL,undefined);
   }
   function removeTradeChannel()
   {
      this.chat.removeChannel(undefined,lol.core.Chat.CHAT_TRADE_CHANNEL);
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_TRADE_CHANNEL,undefined,"main");
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_TRADE_CHANNEL,undefined,"stack");
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
   }
   function createWorldChannel()
   {
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_WORLD_CHANNEL,undefined);
   }
   function removeWorldChannel()
   {
      this.chat.removeChannel(undefined,lol.core.Chat.CHAT_WORLD_CHANNEL);
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_WORLD_CHANNEL,undefined,"main");
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_WORLD_CHANNEL,undefined,"stack");
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
   }
   function createHelpChannel()
   {
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_HELP_CHANNEL,undefined);
   }
   function removeHelpChannel()
   {
      this.chat.removeChannel(undefined,lol.core.Chat.CHAT_HELP_CHANNEL);
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_HELP_CHANNEL,undefined,"main");
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_HELP_CHANNEL,undefined,"stack");
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
   }
   function createEventChannel()
   {
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_EVENT_CHANNEL,undefined);
   }
   function removeEventChannel()
   {
      this.chat.removeChannel(undefined,lol.core.Chat.CHAT_EVENT_CHANNEL);
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_EVENT_CHANNEL,undefined,"main");
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_EVENT_CHANNEL,undefined,"stack");
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
   }
   function checkClan()
   {
      this.clanInspector = lol.core.clans.ClanInspector.getInstance();
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.clanUpdate);
      if(this.master.playerRegister.gamer.clanMemberInfo.clanInfo.reg != 0 && this.master.playerRegister.gamer.clanMemberInfo.clanInfo.reg != 16777215)
      {
         if(this.checkAllowViewChat())
         {
            this.initClanChannel();
         }
      }
      else
      {
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_SUCCES,this,this.clanInvite);
      }
   }
   function checkParty()
   {
      this.partyManager = lol.core.party.PartyManager.getInstance();
      this.partyManager.addEventListener(lol.core.party.PartyEvent.PARTY_LIST_REFRESH,this,this.partyUpdate);
      this.partyManager.addEventListener(lol.core.party.PartyEvent.JOIN_TO_PARTY,this,this.partyUpdate);
      if(this.partyManager.hasParty())
      {
         this.initPartyChannel();
      }
      else
      {
         this.removePartyChannel();
      }
   }
   function initClanChannel()
   {
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_CLAN_CHANNEL,undefined);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.KICKED_FROM_CLAN,this,this.kickedFromClan);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES,this,this.clanLeave);
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
   }
   function initPartyChannel()
   {
      this.chatChannelPan.newChannel(lol.core.Chat.CHAT_PARTY_CHANNEL,undefined);
      this.partyManager.addEventListener(lol.core.party.PartyEvent.DISBAND_PARTY,this,this.disbandParty);
      this.partyManager.addEventListener(lol.core.party.PartyEvent.LEAVE_PARTY,this,this.leaveParty);
      this.partyManager.addEventListener(lol.core.party.PartyEvent.PARTY_LEADER_CHANGED,this,this.partyLeaderChanged);
      this.partyManager.addEventListener(lol.core.party.PartyEvent.PLAYER_DISCONNECTED,this,this.playerDisconnected);
      this.partyManager.addEventListener(lol.core.party.PartyEvent.PLAYER_RETURN_ONLINE,this,this.playerReturnOnline);
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
      this.showPartyButton();
   }
   function playerDisconnected(obj)
   {
      var _loc3_ = this.partyList.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data.id == obj.target.data.id)
         {
            _loc3_[_loc2_].offlineFill.gotoAndStop(2);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function playerReturnOnline(obj)
   {
      var _loc3_ = this.partyList.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data.id == obj.target.data.id)
         {
            _loc3_[_loc2_].offlineFill.gotoAndStop(1);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function showPartyButton()
   {
      this.PartyButton_Visible = true;
      this.resizeStage({w:Stage.width,h:Stage.height});
   }
   function hidePartyButton()
   {
      this.PartyButton_Visible = false;
      this.resizeStage({w:Stage.width,h:Stage.height});
   }
   function showPartyPanel()
   {
      this.PartyPanel_Visible = true;
      this.resizeStage({w:Stage.width,h:Stage.height});
   }
   function hidePartyPanel()
   {
      this.PartyPanel_Visible = false;
      this.resizeStage({w:Stage.width,h:Stage.height});
   }
   function showHidePartyPan()
   {
      this.PartyPanel_Visible = !this.PartyPanel_Visible;
      this.resizeStage({w:Stage.width,h:Stage.height});
   }
   function disbandParty(obj)
   {
      obj.target.removeEventListener(lol.core.party.PartyEvent.DISBAND_PARTY,this,this.disbandParty);
      obj.target.removeEventListener(lol.core.party.PartyEvent.LEAVE_PARTY,this,this.leaveParty);
      obj.target.removeEventListener(lol.core.party.PartyEvent.PARTY_LEADER_CHANGED,this,this.partyLeaderChanged);
      this.removePartyChannel();
      this.clearPartyPanel();
      this.PartyButton_Visible = false;
      this.PartyPanel_Visible = false;
      this.resizeStage({w:Stage.width,h:Stage.height});
   }
   function clearPartyPanel()
   {
      var _loc3_ = this.partyList.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         _loc3_[_loc2_].removeEventListener("openPartyPlayerMenu",this);
         _loc2_ = _loc2_ + 1;
      }
      this.partyList.clearList();
   }
   function leaveParty(obj)
   {
      this.removePartyPlayer(obj);
   }
   function refreshPartyList()
   {
      this.clearPartyPanel();
      this.partyInitialize();
   }
   function partyLeaderChanged(obj)
   {
      this.refreshPartyList();
   }
   function removeClanChannel()
   {
      var _loc2_ = this.chatChannelPan.getChannel(lol.core.Chat.CHAT_CLAN_CHANNEL,undefined);
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_CLAN_CHANNEL,undefined,"main");
      this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_CLAN_CHANNEL,undefined,"stack");
      this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_SUCCES,this,this.clanInvite);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.initClanChannel);
   }
   function removePartyChannel()
   {
      var _loc2_ = this.chatChannelPan.getChannel(1,undefined);
      if(_loc2_)
      {
         this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_PARTY_CHANNEL,undefined,"main");
         this.chatChannelPan.removeChannel(lol.core.Chat.CHAT_PARTY_CHANNEL,undefined,"stack");
         this.chatChannelPan.initChannel(lol.core.Chat.CHAT_LOCATION_CHANNEL,undefined);
      }
   }
   function clanInvite(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_SUCCES,this,this.clanInvite);
      if(this.checkAllowViewChat())
      {
         this.initClanChannel();
      }
   }
   function kickedFromClan(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.KICKED_FROM_CLAN,this,this.kickedFromClan);
      this.removeClanChannel();
   }
   function clanLeave(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES,this,this.clanLeave);
      this.removeClanChannel();
   }
   function clanUpdate(obj)
   {
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc4_ = _loc3_.rights;
      var _loc2_ = this.chatChannelPan.getChannel(2,undefined);
      this.clanMemberList = lol.core.clans.ClanInspector.getInstance().getClanMemberList();
      if(this.checkAllowViewChat())
      {
         if(_loc2_ == undefined)
         {
            this.initClanChannel();
         }
      }
      else if(_loc2_ != undefined)
      {
         this.removeClanChannel();
      }
   }
   function partyUpdate(obj)
   {
      var _loc2_ = this.chatChannelPan.getChannel(lol.core.Chat.CHAT_PARTY_CHANNEL,undefined);
      if(_loc2_ == undefined)
      {
         this.initPartyChannel();
      }
      this.showPartyButton();
      this.refreshPartyList();
   }
   function checkAllowViewChat()
   {
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      return _loc2_.allowChatAndViewStandings;
   }
   function initChannel(group, withID)
   {
      this.chatChannelPan.initChannel(group,withID);
   }
   function kill()
   {
      lol.core.SceneShifter.chat.removeEventListener("addPlayer",lol.core.SceneShifter.hintManager);
      lol.core.SceneShifter.chat.removeEventListener("removePlayer",lol.core.SceneShifter.hintManager);
      this.userList.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.__selectUser);
      this.partyListPan.hidePartyPan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showHidePartyPan);
      this.globalMap.removeEventListener("addPlayer",this);
      this.globalMap.removeEventListener("removePlayer",this);
      this.location.removeEventListener("addPlayer",this);
      this.location.removeEventListener("removePlayer",this);
      this.chat.removeEventListener("refresh",this);
      this.scrBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrollUp);
      this.scrBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrollDown);
      this.scrBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.stopScroll);
      this.scrBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.stopScroll);
      lol.core.SceneShifter._ref.removeEventListener("resizeStage",this);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CHAT_IN_FOCUS,this);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.ESC,this);
      lol.core.SceneShifter.hintManager.deleteHint(lol.gpui.HintManager.SHOW_TIME);
      lol.core.SceneShifter.hintManager.deleteHint(lol.gpui.HintManager.CLEAR_CHAT);
      this.send_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sendMessage);
   }
   function refresh(disObj)
   {
      this.chatChannelPan.newMessage(disObj.group,disObj.withID);
   }
   function showChannel(obj)
   {
      var _loc3_ = this.chat.getChannel(obj.group,obj.withID);
      this.showMessage(_loc3_.logArr,obj.group);
      if(obj.group == lol.core.Chat.CHAT_EVENT_CHANNEL)
      {
         this.inputEnabled = false;
      }
      else
      {
         this.inputEnabled = true;
      }
   }
   function startChat(obj)
   {
      if(obj.target.data.id)
      {
         this.chatInput.text = "private " + lol.core.Master.getInstance().getPlayer(obj.target.data.id).playerInfo.name + ": ";
         this.gotoLastSymbol();
      }
   }
   function startInspect(obj)
   {
      var _loc1_;
      if(lol.core.Master.getInstance().currentState == lol.core.Master.LOCAL_STATE && obj.target.data.id != lol.core.player.Gamer.ID)
      {
         lol.core.SceneShifter.closeWindow("inspect");
         _loc1_ = lol.core.SceneShifter.openNewWindow("inspect");
         _loc1_.content.setPlayer(obj.target.data.id);
      }
   }
   function openPartyPlayerMenu(obj)
   {
      if(obj.target.data.id != undefined)
      {
         this.contextMenuPlayer = obj.target.data;
         if(this.partyManager.weAreLeader())
         {
            if(obj.target.data.id == 0)
            {
               this.createSelfContextMenu();
            }
            else
            {
               this.createPartyLeaderContextMenu();
            }
         }
         else if(obj.target.data.id == 0)
         {
            this.createSelfContextMenu();
         }
         else
         {
            this.createPartyPlayerContextMenu();
         }
      }
   }
   function createSelfContextMenu()
   {
      var _loc2_ = new Array();
      _loc2_.push({linkID:"actionLeaveGroup_btn",obj:this,function_str:"actionLeaveGroup",data:this.contextMenuPlayer.id});
      lol.core.SceneShifter.contextMenuManager.openContextMenu(_loc2_,"actionDropList",this.contextMenuPlayer.playerInfo.name);
      lol.core.SceneShifter.contextMenuManager.addEventListener("selectItem",this,this.clickContext);
      delete lol.core.SceneShifter.linkWindow.onMouseUp;
      delete this.contextMenuPlayer;
   }
   function createPartyLeaderContextMenu()
   {
      var _loc2_ = new Array();
      _loc2_.push({linkID:"actionPrivat_btn",obj:this,function_str:"actionPrivat",data:this.contextMenuPlayer.id});
      _loc2_.push({linkID:"actionDeleteFromParty_btn",obj:this,function_str:"actionDeleteFromParty",data:this.contextMenuPlayer.id});
      _loc2_.push({linkID:"actionPassLeadership_btn",obj:this,function_str:"actionPassLeadership",data:this.contextMenuPlayer.id});
      _loc2_.push({linkID:"actionLeaveGroup_btn",obj:this,function_str:"actionLeaveGroup",data:this.contextMenuPlayer.id});
      lol.core.SceneShifter.contextMenuManager.openContextMenu(_loc2_,"actionDropList",this.contextMenuPlayer.playerInfo.name);
      lol.core.SceneShifter.contextMenuManager.addEventListener("selectItem",this,this.clickContext);
      delete lol.core.SceneShifter.linkWindow.onMouseUp;
      delete this.contextMenuPlayer;
   }
   function createPartyPlayerContextMenu()
   {
      var _loc2_ = new Array();
      _loc2_.push({linkID:"actionPrivat_btn",obj:this,function_str:"actionPrivat",data:this.contextMenuPlayer.id});
      _loc2_.push({linkID:"actionLeaveGroup_btn",obj:this,function_str:"actionLeaveGroup",data:this.contextMenuPlayer.id});
      lol.core.SceneShifter.contextMenuManager.openContextMenu(_loc2_,"actionDropList",this.contextMenuPlayer.playerInfo.name);
      lol.core.SceneShifter.contextMenuManager.addEventListener("selectItem",this,this.clickContext);
      delete lol.core.SceneShifter.linkWindow.onMouseUp;
      delete this.contextMenuPlayer;
   }
   function clickContext(obj)
   {
      obj.target.removeEventListener("selectItem",this,this.clickContext);
      var _loc3_;
      if(obj.data.function_str == "actionPrivat")
      {
         lol.core.SceneShifter.chat.chatChannelPan.newChannel(undefined,obj.data.param);
      }
      else if(obj.data.function_str == "actionDeleteFromParty")
      {
         _loc3_ = new lol.server.mess.CSM_P_OP(lol.core.party.PartyManager.PARTY_SEND_KICK_PLAYER,obj.data.param);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.ResultKickPlayer,obj.data.param);
         }
      }
      else if(obj.data.function_str == "actionPassLeadership")
      {
         _loc3_ = new lol.server.mess.CSM_P_OP(lol.core.party.PartyManager.PARTY_SEND_CHANGE_LEADER,obj.data.param);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.ResultSendChangeLeader,obj.data.param);
         }
      }
      else if(obj.data.function_str == "actionLeaveGroup")
      {
         _loc3_ = new lol.server.mess.CSM_P_OP(lol.core.party.PartyManager.PARTY_SEND_KICK_PLAYER,0);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.ResultLeaveGroup,obj.data.param);
         }
         else
         {
            trace("not send!");
         }
      }
   }
   function ResultKickPlayer(obj)
   {
      var _loc2_;
      if(obj.param.res != 0)
      {
         _loc2_ = lol.core.SceneShifter.openNewWindow("alert","center");
         _loc2_.content.write("Игрок не может быть изгнан из отряда");
      }
      else
      {
         this.refreshPartyList();
      }
   }
   function ResultSendChangeLeader(obj)
   {
      var _loc2_;
      if(obj.param.res != 0)
      {
         _loc2_ = lol.core.SceneShifter.openNewWindow("alert","center");
         _loc2_.content.write("Вы не смогли поменять лидера отряда");
      }
      else
      {
         this.refreshPartyList();
      }
   }
   function ResultLeaveGroup(obj)
   {
      var _loc3_;
      if(obj.param.res != 0)
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert","center");
         _loc3_.content.write("Вы не смогли выйти из группы");
      }
      else
      {
         this.clearPartyPanel();
         this.partyManager.leaveParty(0);
         this.PartyButton_Visible = false;
         this.PartyPanel_Visible = false;
         this.resizeStage({w:Stage.width,h:Stage.height});
      }
   }
   function showMessage(messArr, group)
   {
      this.tempMessArr = messArr;
      this.chatOutput.htmlText = "";
      var _loc16_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_MESSAGE);
      var _loc17_ = messArr.length - _loc16_ <= 0 ? 0 : messArr.length - _loc16_;
      if(_loc17_ > 0)
      {
         messArr.splice(0,_loc17_);
      }
      var _loc4_ = 0;
      var _loc3_;
      var _loc8_;
      var _loc2_;
      var _loc6_;
      var _loc11_;
      var _loc7_;
      var _loc12_;
      var _loc15_;
      var _loc9_;
      var _loc10_;
      var _loc13_;
      var _loc14_;
      while(_loc4_ < messArr.length)
      {
         _loc3_ = messArr[_loc4_].mess;
         _loc8_ = messArr[_loc4_].fromID;
         _loc2_ = messArr[_loc4_].name;
         _loc6_ = messArr[_loc4_].group;
         _loc11_ = messArr[_loc4_].withID;
         _loc7_ = "";
         if(_loc11_)
         {
            _loc7_ = this.getName(_loc11_);
         }
         else
         {
            _loc7_ = messArr[_loc4_].to_name;
         }
         _loc12_ = this.master.playerRegister.gamer.playerInfo.name;
         if(_loc8_ == "server")
         {
            if(_loc6_ != lol.core.Chat.CHAT_TRADE_CHANNEL && _loc6_ != lol.core.Chat.CHAT_HELP_CHANNEL && _loc6_ != lol.core.Chat.CHAT_WORLD_CHANNEL)
            {
               _loc2_ = _loc8_;
            }
            else
            {
               _loc2_ = _loc12_;
            }
         }
         else if(_loc8_ == "events")
         {
            _loc2_ = "events";
         }
         else if(_loc2_ == undefined)
         {
            _loc2_ = this.getName(_loc8_);
         }
         _loc9_ = "";
         if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TIME_IN_CHAT))
         {
            _loc9_ = " " + messArr[_loc4_].time + " ";
         }
         _loc10_ = _loc3_.indexOf(":",0);
         _loc13_ = false;
         if(_loc8_ != undefined && (_loc6_ == undefined || _loc6_ == lol.core.Chat.CHAT_PRIVATE_CHANNEL))
         {
            _loc13_ = true;
         }
         if(_loc10_ != -1)
         {
            _loc14_ = _loc3_.substring(3,_loc10_);
            if(_loc14_ == this.master.gamer.playerInfo.name)
            {
               _loc3_ = "<b><i>" + _loc3_.substr(0,_loc10_ + 1) + "</i></b> " + _loc3_.substring(_loc10_ + 1,_loc3_.length);
            }
         }
         if(_loc2_ == "events")
         {
            this.chatOutput.htmlText += _loc9_ + _loc3_ + "\r";
         }
         else if(_loc2_ == "server")
         {
            this.chatOutput.htmlText += "Персонаж находится в офлайне.\rОтправьте Ваше сообщение повторно после его возвращения в игру или <A HREF=\"asfunction:goToMailInterface\"><U>напишите ему письмо</U></A> \r";
         }
         else if(_loc13_)
         {
            if(_loc7_)
            {
               this.chatOutput.htmlText += _loc9_ + " " + "<b><font color=\'#343f15\'><A HREF=\"asfunction:selectPrivateUserNick," + _loc7_ + "\">[" + _loc2_ + "] private [" + _loc7_ + "]</b>:</A></font> " + _loc3_ + "\r";
            }
            else
            {
               this.chatOutput.htmlText += _loc9_ + " " + "<b><font color=\'#343f15\'><A HREF=\"asfunction:selectPrivateUserNick," + _loc2_ + "\">[" + _loc2_ + "] private [" + _loc12_ + "]:</b></A></font> " + _loc3_ + "\r";
            }
         }
         else
         {
            this.chatOutput.htmlText += _loc9_ + " " + "<A HREF=\"asfunction:selectUserNick," + _loc2_ + "\"><b>[" + _loc2_ + "]:</b></A> " + _loc3_ + "\r";
         }
         _loc4_ = _loc4_ + 1;
      }
      this.chatOutput.scroll += 1000;
   }
   function selectUserNickBase(name_str, first_word)
   {
      var _loc3_ = this.chatInput.text;
      var _loc4_ = "private ";
      var _loc5_ = "to ";
      var _loc9_ = _loc3_.indexOf(_loc5_,0);
      var _loc2_ = _loc3_.indexOf(":",0);
      var _loc11_;
      var _loc7_;
      var _loc8_;
      if(_loc9_ == 0 && _loc2_ > 0)
      {
         _loc11_ = new String();
         _name = _loc3_.slice(_loc9_ + _loc5_.length,_loc2_);
         _loc2_ -= _loc5_.length;
         while(_name.charAt(0) == " ")
         {
            _name = _name.slice(1);
            _loc2_ = _loc2_ - 1;
         }
         _loc7_ = new String();
         _loc7_ = _loc3_.slice(_loc2_ + _loc5_.length + 2);
         if(_name == name_str)
         {
            this.chatInput.text = _loc4_ + name_str + ": " + _loc7_;
            this.gotoLastSymbol();
         }
         else
         {
            this.chatInput.text = first_word + name_str + ": " + _loc7_;
            this.gotoLastSymbol();
         }
      }
      else
      {
         _loc8_ = _loc3_.indexOf(_loc4_,0);
         if(_loc8_ == 0 && _loc2_ > 0)
         {
            _loc11_ = new String();
            _name = _loc3_.slice(_loc8_ + _loc4_.length,_loc2_);
            _loc2_ -= _loc4_.length;
            while(_name.charAt(0) == " ")
            {
               _name = _name.slice(1);
               _loc2_ = _loc2_ - 1;
            }
            _loc7_ = new String();
            _loc7_ = _loc3_.slice(_loc2_ + _loc4_.length + 2);
            if(_name == name_str)
            {
               this.chatInput.text = _loc5_ + name_str + ": " + _loc7_;
               this.gotoLastSymbol();
            }
            else
            {
               this.chatInput.text = _loc4_ + name_str + ": " + _loc7_;
               this.gotoLastSymbol();
            }
         }
         else
         {
            this.chatInput.text = first_word + name_str + ": " + _loc3_;
            this.gotoLastSymbol();
         }
      }
   }
   function selectUserNick(name_str)
   {
      var _loc2_ = "to ";
      this.selectUserNickBase(name_str,_loc2_);
   }
   function selectPrivateUserNick(name_str)
   {
      var _loc2_ = "private ";
      this.selectUserNickBase(name_str,_loc2_);
   }
   function gotoLastSymbol()
   {
      Selection.setFocus(this.chatInput);
      var _loc2_ = this.chatInput.text.length;
      Selection.setSelection(_loc2_,_loc2_);
   }
   function refreshCurrentChannel()
   {
      this.showMessage(this.tempMessArr);
   }
   function goToMailInterface()
   {
      var _loc2_ = lol.core.SceneShifter._ref.currentScene.mail_btn;
      lol.core.SceneShifter._ref.currentScene.openCloseSlideWindow({target:_loc2_});
      var _loc3_ = new lol.utils.Timeout(this,this.openNewLetterPage,1500);
   }
   function openNewLetterPage()
   {
      var _loc1_ = lol.core.SceneShifter._sl.getWindow("mailInterface").content;
      _loc1_.selectPageExt(_loc1_.newLetter_btn);
   }
   function getName(fromID)
   {
      if(fromID == "Подсказка")
      {
         return fromID;
      }
      var _loc2_ = this.chat.getName(fromID);
      return _loc2_;
   }
   function sendMessage(obj, _messStr)
   {
      var _loc3_ = _messStr != undefined ? _messStr : this.chatInput.text;
      var _loc6_;
      _loc6_ = "";
      var _loc7_ = false;
      var _loc2_;
      var _loc4_;
      var _loc5_;
      var _loc9_;
      var _loc8_;
      var _loc10_;
      var _loc12_;
      if(_loc3_.length > 0 && this.sendAllow)
      {
         if(_loc3_.length <= 80)
         {
            _loc2_ = new Object();
            _loc4_ = "private ";
            _loc5_ = _loc3_.indexOf(_loc4_,0);
            if(_loc5_ >= 0)
            {
               _loc9_ = _loc3_.indexOf(":",_loc5_);
               this._name = _loc3_.slice(_loc5_ + _loc4_.length,_loc9_);
               _loc2_.to = this._name;
               _loc6_ = _loc4_ + this._name + ": ";
               _loc8_ = new String();
               _loc8_ = _loc3_.slice(0,_loc5_) + _loc3_.slice(_loc9_ + 2);
               this.LastString = _loc4_ + this._name + ": ";
               _loc2_.mess = _loc8_;
            }
            else
            {
               _loc2_.group = this.chatChannelPan.currentChannel.group;
               _loc2_.toID = this.chatChannelPan.currentChannel.withID;
               _loc2_.mess = _loc3_;
            }
            if(_loc2_.group == lol.core.Chat.CHAT_PRIVATE_CHANNEL && _loc2_.toID == undefined)
            {
               _loc7_ = true;
            }
            if(!_loc7_)
            {
               this.chat.sendMessage(_loc2_);
               this.chatOutput.scroll += 1000;
               if(_messStr == undefined)
               {
                  this.sendAllow = false;
                  _loc10_ = _loc2_.group != lol.core.Chat.CHAT_TRADE_CHANNEL ? this.TIME_OUT : this.TRADE_TIME_OUT;
                  _loc12_ = new lol.utils.Timeout(this,this.sendAllow_func,_loc10_);
               }
            }
            else
            {
               lol.utils.ErrorReport.callReport(0,1001);
            }
         }
         else
         {
            this.sendInStack(this.chatInput.text);
         }
         this.chatInput.text = "";
         trace("tempStr.length = " + this.tempStr.length + ", nameToRestore = " + _loc6_);
         Selection.setSelection(_loc6_.length,_loc6_.length);
      }
   }
   function sendAllow_func()
   {
      this.sendAllow = true;
   }
   function sendInStack(str)
   {
      var _loc3_ = str;
      this.stackArr = new Array();
      var _loc4_ = 0;
      var _loc7_ = "private ";
      var _loc9_ = "";
      var _loc5_ = 70;
      var _loc6_ = _loc3_.indexOf(_loc7_,0);
      var _loc8_;
      if(_loc6_ >= 0)
      {
         _loc8_ = _loc3_.indexOf(":",_loc6_);
         if(_loc8_ >= 0)
         {
            _name = _loc3_.slice(_loc6_ + _loc7_.length,_loc8_);
            _loc5_ = 62 - _name.length;
         }
         else
         {
            _name = "";
         }
      }
      else
      {
         _name = "";
      }
      var _loc2_;
      while(_loc3_.length > _loc5_)
      {
         _loc2_ = _loc3_.substring(0,_loc5_);
         _loc3_ = _loc3_.substring(_loc5_,_loc3_.length);
         if(_name.length > 0 && _loc4_ > 0)
         {
            _loc2_ = "private " + _name + ": " + _loc2_;
         }
         _loc2_ = "^" + _loc4_ + "^" + _loc2_;
         _loc4_ = _loc4_ + 1;
         this.stackArr.push(_loc2_);
      }
      if(_loc4_ > 0)
      {
         if(_name != "")
         {
            _loc3_ = "^" + _loc4_ + "L^" + "private " + _name + ": " + _loc3_;
         }
         else
         {
            _loc3_ = "^" + _loc4_ + "L^" + _loc3_;
         }
      }
      this.stackArr.push(_loc3_);
      this.chat.addEventListener("deliver",this,this.deliverMessage);
      this.sendMessageWithPause();
   }
   function sendMessageWithPause()
   {
      var _loc2_ = this.stackArr.shift();
      this.sendMessage(undefined,_loc2_);
   }
   function deliverMessage()
   {
      this.sendMessageWithPause();
      if(this.stackArr.length == 0)
      {
         this.chat.removeEventListener("deliver",this,this.deliverMessage);
      }
   }
   function showCursor(fl)
   {
      var _loc3_ = this.main.getNextHighestDepth();
      var _loc2_;
      if(fl)
      {
         if(!this.main.resizeCursor)
         {
            _loc2_ = this.main.attachMovie("resizeCursor","resizeCursor",_loc3_);
            _loc2_._x = this.main._xmouse;
            _loc2_._y = this.main._ymouse;
            _loc2_.onMouseMove = mx.utils.Delegate.create(this,this.moveCursor);
            Mouse.hide();
         }
      }
      else
      {
         Mouse.show();
         delete _loc2_.onMouseMove;
         this.main.resizeCursor.removeMovieClip();
      }
   }
   function moveCursor()
   {
      var _loc2_ = this.main.resizeCursor;
      _loc2_._x = this.main._xmouse;
      _loc2_._y = this.main._ymouse;
   }
   function startResize()
   {
      var _loc2_ = lol.core.SceneShifter.chat._y - lol.core.SceneShifter._ref.minScreenH;
      this.chatResize.startDrag(false,0,- _loc2_,0,0);
      this.chatResize.onMouseMove = mx.utils.Delegate.create(this,this.dragChatResize);
      this.isDrag = true;
   }
   function stopResize()
   {
      this.dragChatResize();
      delete this.chatResize.onMouseMove;
      this.chatResize.stopDrag();
      this.isDrag = false;
   }
   function stopResizeOut()
   {
      this.showCursor(false);
      delete this.chatResize.onMouseMove;
      this.stopResize();
      this.isDrag = false;
   }
   function dragChatResize(b)
   {
      var _loc3_ = lol.core.SceneShifter.chat._y + this.chatResize._y;
      var _loc2_ = this.chatResize._y;
      this.back._y = _loc2_;
      this.back.backTop._height = 138 - _loc2_ - 16;
      this.chatListPan._y = 6 + _loc2_;
      this.chatListPan.bottom._y = 98 - _loc2_;
      this.chatListPan.mask._height = this.chatListPan.bottom._y;
      this.channelPan._y = _loc2_;
      this.partyListPan._y = 6 + _loc2_;
      this.partyListPan.bottom._y = 103 - _loc2_;
      this.partyListPan.mask._height = this.partyListPan.bottom._y - 6;
      this.chatListPan.shadowLeft._height = this.chatListPan.mask._height - 18;
      this.chatListPan.shadowRight._height = this.chatListPan.mask._height - 18;
      this.chatListPan.userList.setSize(165,this.chatListPan.mask._height - 16);
      this.partyListPan.partyList.setSize(142,this.partyListPan.mask._height);
      this.scrBar._y = 25 + _loc2_;
      this.time_btn._y = this.scrBar._y + 10;
      this.erase_btn._y = this.time_btn._y + 25;
      this.chatOutput._y = 24 + _loc2_;
      if(this.inputEnabled)
      {
         this.chatOutput._height = 70 - _loc2_;
         this.scrBar.setSize(this.chatOutput._height - 2);
      }
      else
      {
         this.chatOutput._height = 93 - _loc2_;
         this.scrBar.setSize(this.chatOutput._height - 2);
      }
      this.line_top.mask._height = 93 - this.chatResize._y;
      this.listPanCont_mc._y = _loc3_;
      if(b == undefined)
      {
         lol.core.SceneShifter.stageShift = - _loc2_;
         lol.core.SceneShifter._ref.setMCSize();
      }
   }
   function resizeStage(obj)
   {
      var _loc5_ = 1040;
      var _loc4_ = 720;
      this.back._width = obj.w - 40;
      this.backBottom._width = obj.w - 40;
      this.chatResize._width = this.back._width;
      this.chatListPan._x = obj.w - 245;
      var _loc2_ = 0;
      if(this.PartyPanel_Visible)
      {
         _loc2_ = 182;
         this.partyListPan._x = this.chatListPan._x - _loc2_;
      }
      else if(this.PartyButton_Visible)
      {
         _loc2_ = this.partyListPan.hidePartyPan_btn._width - 1;
         this.partyListPan._x = this.chatListPan._x - _loc2_;
      }
      else
      {
         _loc2_ = 0;
         this.partyListPan._x = this.chatListPan._x;
      }
      this.channelPan.right._x = obj.w - 248 - _loc2_;
      this.channelPan.back._width = this.channelPan.right._x - this.channelPan.back._x - 35;
      this.channelPan.mask._width = this.channelPan.back._width;
      this.send_btn._x = obj.w - 372 - _loc2_;
      this.chatOutput._width = this.send_btn._x - this.chatOutput._x + this.send_btn._width - 20;
      this.chatInput._width = this.send_btn._x - this.chatInput._x;
      this.scrBar._x = this.send_btn._x + 63;
      this.time_btn._x = this.scrBar._x + 20;
      this.erase_btn._x = this.scrBar._x + 20;
      this.line_top._width = this.chatOutput._width + 30;
      this.chatChannelPan.setSize(this.chatOutput._width + 20);
      this.chatChannelPan.resizeStage();
      this.line_bottom._width = this.chatInput._width;
      if(!this.isDrag)
      {
         this.chatResize._y = - lol.core.SceneShifter.tempChatShift;
      }
      this.dragChatResize(false);
      this.line_top.mask._height = 93 - this.chatResize._y;
   }
   function set inputEnabled(value)
   {
      if(value)
      {
         this.line_bottom._visible = true;
         this.send_btn._visible = true;
         this.chatInput._visible = true;
         this.line_top._y = 93;
         this.chatOutput._height = 70 - this.chatResize._y;
         this.scrBar.setSize(this.chatOutput._height - 2);
      }
      else
      {
         this.line_bottom._visible = false;
         this.send_btn._visible = false;
         this.chatInput._visible = false;
         this.line_top._y = 116;
         this.chatOutput._height = 93 - this.chatResize._y;
         this.scrBar.setSize(this.chatOutput._height - 2);
      }
   }
   function get inputEnabled()
   {
      return this.send_btn._visible;
   }
   function scrollUp()
   {
      this.flag = true;
   }
   function scrollDown()
   {
      this.flag = true;
   }
   function stopScroll()
   {
      this.flag = false;
   }
   function scrollText()
   {
      var _loc2_;
      if(this.scrBar.sliderButton.onMouseMove == undefined && !this.flag)
      {
         _loc2_ = (this.chatOutput.scroll - 1) * 100 / this.chatOutput.maxscroll;
         if(this.chatOutput.maxscroll == this.chatOutput.scroll)
         {
            _loc2_ = 100;
         }
         if(_loc2_ < 100)
         {
            this.scrBar.__position = _loc2_;
         }
         else
         {
            this.scrBar.__position = 100;
         }
      }
      this.chekTextSize();
   }
   function chekTextSize()
   {
      if(this.chatOutput.textHeight + 10 > this.chatOutput._height)
      {
         this.scrBar._visible = true;
      }
      else
      {
         this.scrBar._visible = false;
      }
   }
   function __selectUser(obj)
   {
      var _loc2_;
      var _loc4_;
      if(obj.item.toggled)
      {
         _loc2_ = obj.item.data;
         _loc4_ = obj.item.toggled;
         this.tempID = _loc2_.id;
      }
      else
      {
         this.tempID = undefined;
      }
   }
   function onKeyDown()
   {
      if(Key.isDown(13))
      {
         this.sendMessage();
      }
   }
   function initUsers()
   {
      this.globalMap.removeEventListener("addPlayer",this);
      this.globalMap.removeEventListener("removePlayer",this);
      this.globalMap = null;
      this.location.removeEventListener("addPlayer",this);
      this.location.removeEventListener("removePlayer",this);
      this.location = null;
      lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.SHOW_TIME,this.time_btn);
      lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.CLEAR_CHAT,this.erase_btn);
      this.userList.clearList();
      this.partyList.clearList();
      lol.core.SceneShifter.chat.removeEventListener("addPlayer",lol.core.SceneShifter.hintManager);
      lol.core.SceneShifter.chat.removeEventListener("removePlayer",lol.core.SceneShifter.hintManager);
      lol.core.SceneShifter.chat.addEventListener("addPlayer",lol.core.SceneShifter.hintManager);
      lol.core.SceneShifter.chat.addEventListener("removePlayer",lol.core.SceneShifter.hintManager);
      this.userList.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.__selectUser);
      this.userList.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.__selectUser);
      lol.core.SceneShifter.hintManager.removeHint(lol.gpui.HintManager.SEND_MESSAGE,this.send_btn);
      var _loc4_ = lol.core.Master.getInstance();
      var _loc3_;
      var _loc2_;
      if(_loc4_.currentState == lol.core.Master.GLOBAL_STATE)
      {
         this.globalMap = _loc4_.globalMap;
         for(var _loc5_ in this.globalMap.playerList)
         {
            _loc3_ = this.globalMap.playerList[_loc5_];
            this.addPlayer({player:_loc3_});
         }
         this.globalMap.removeEventListener("addPlayer",this);
         this.globalMap.removeEventListener("removePlayer",this);
         this.globalMap.addEventListener("addPlayer",this);
         this.globalMap.addEventListener("removePlayer",this);
      }
      else if(_loc4_.currentState == lol.core.Master.LOCAL_STATE)
      {
         this.location = _loc4_.currentLocation;
         for(_loc5_ in this.location.playerList)
         {
            _loc2_ = this.location.playerList[_loc5_];
            this.addPlayer({player:_loc2_});
         }
         this.location.removeEventListener("addPlayer",this);
         this.location.removeEventListener("removePlayer",this);
         this.location.addEventListener("addPlayer",this);
         this.location.addEventListener("removePlayer",this);
      }
      this.partyInitialize();
   }
   function partyInitialize()
   {
      var _loc7_ = lol.core.Master.getInstance();
      var _loc8_ = _loc7_.gamer;
      var _loc4_;
      var _loc5_;
      var _loc2_;
      var _loc3_;
      if(_loc8_)
      {
         _loc4_ = _loc8_.partyManager;
         _loc5_ = true;
         _loc2_ = 0;
         while(_loc2_ < _loc4_.GroupList.length)
         {
            _loc3_ = _loc7_.getPlayer(_loc4_.GroupList[_loc2_]);
            this.addPartyPlayer({player:_loc3_},_loc5_);
            _loc5_ = false;
            _loc2_ = _loc2_ + 1;
         }
      }
   }
   function addPlayer(obj)
   {
      var _loc2_ = obj.player;
      var _loc7_ = _loc2_.id;
      var _loc5_ = _loc2_.playerInfo;
      var _loc4_;
      var _loc3_;
      if(_loc2_ instanceof lol.core.player.Player)
      {
         if(_loc5_.name)
         {
            _loc4_ = "[" + _loc2_.attributes.level + "] " + _loc5_.name;
         }
         else
         {
            _loc4_ = _loc2_.id;
         }
         _loc2_.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
         _loc3_ = this.userList.addItem({label:_loc4_,data:_loc2_});
         this.dispatchEvent({type:"addPlayer",mc:_loc3_});
         _loc3_.addEventListener("startChat",this);
         if(lol.core.Master.getInstance().currentState == lol.core.Master.LOCAL_STATE)
         {
            _loc3_.addEventListener("startInspect",this);
         }
         else
         {
            this.doLater("doEnabled",[_loc3_.startInspect_btn]);
         }
      }
   }
   function addPartyPlayer(obj, isFirstPlayer)
   {
      var _loc2_ = obj.player;
      if(!_loc2_)
      {
         return undefined;
      }
      var _loc7_ = _loc2_.id;
      var _loc5_ = _loc2_.playerInfo;
      var _loc4_;
      var _loc3_;
      if(_loc2_ instanceof lol.core.player.Player)
      {
         if(_loc5_.name)
         {
            _loc4_ = "[" + _loc2_.attributes.level + "] " + _loc5_.name;
         }
         else
         {
            _loc4_ = _loc2_.id;
         }
         _loc2_.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.partyUserInfoUpdate);
         _loc2_.addEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.partyUserInfoUpdate);
         _loc3_ = this.partyList.addItem({label:_loc4_,data:_loc2_});
         _loc3_.setLeader(isFirstPlayer);
         _loc3_.addEventListener("openPartyPlayerMenu",this);
         this.dispatchEvent({type:"addPlayer",mc:_loc3_});
      }
   }
   function doEnabled(btn)
   {
      btn.enabled = false;
   }
   function userInfoUpdate(obj)
   {
      var _loc6_ = lol.core.player.Player(obj.target);
      _loc6_.removeEventListener("uiUpd",this);
      var _loc5_ = _loc6_.id;
      var _loc4_ = "[" + _loc6_.attributes.level + "] " + _loc6_.playerInfo.name;
      var _loc3_ = this.userList.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data.id == _loc5_)
         {
            _loc3_[_loc2_].label = _loc4_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function partyUserInfoUpdate(obj)
   {
      var _loc4_ = lol.core.player.Player(obj.target);
      _loc4_.removeEventListener("uiUpd",this);
      var _loc7_ = _loc4_.id;
      var _loc5_ = "[" + _loc4_.attributes.level + "] " + _loc4_.playerInfo.name;
      var _loc6_ = 100 * _loc4_.health / _loc4_.maxHealth;
      var _loc8_ = 100 * _loc4_.stamina / _loc4_.maxStamina;
      var _loc3_ = this.partyList.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data.id == _loc7_)
         {
            _loc3_[_loc2_].label = _loc5_;
            _loc3_[_loc2_].showHealth(_loc6_);
            _loc3_[_loc2_].showStamina(_loc8_);
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function removePartyPlayer(obj)
   {
      var _loc3_ = obj.body;
      var _loc2_ = this.partyList.getList();
      for(var _loc6_ in _loc2_)
      {
         if(_loc2_[_loc6_].data.id == _loc3_)
         {
            _loc2_[_loc6_].removeEventListener("openPartyPlayerMenu",this);
            this.partyList.removeItem(_loc6_);
            this.refreshPartyList();
            this.dispatchEvent({type:"removePlayer",mc:this.userList.getList()[_loc6_]});
            _loc3_.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.partyUserInfoUpdate);
            _loc3_.removeEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.partyUserInfoUpdate);
            return undefined;
         }
      }
   }
   function userStateUpdate(obj)
   {
      var _loc1_ = obj.target;
      var _loc2_ = _loc1_.playerInfo.name + " <" + _loc1_.attributes.level + ">";
   }
   function rpUpdate(obj)
   {
      var _loc1_ = obj.target;
      var _loc2_ = _loc1_.playerInfo.name + " <" + _loc1_.attributes.level + ">";
   }
   function removePlayer(obj)
   {
      var _loc5_ = obj.player;
      var _loc2_ = this.userList.getList();
      for(var _loc6_ in _loc2_)
      {
         if(_loc2_[_loc6_].data == _loc5_)
         {
            _loc2_[_loc6_].removeEventListener("startChat",this);
            _loc2_[_loc6_].removeEventListener("startInspect",this);
            this.userList.removeItem(_loc6_);
            this.dispatchEvent({type:"removePlayer",mc:this.userList.getList()[_loc6_]});
            return undefined;
         }
      }
   }
   function timeInMessage(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_TIME_IN_CHAT,obj.target.toggled);
      this.refreshCurrentChannel();
   }
   function eraseOutput(obj)
   {
      this.chat.eraseChannel(this.chatChannelPan.currentChannel.withID,this.chatChannelPan.currentChannel.group);
      this.chatOutput.text = "";
      delete this.tempMessArr;
   }
   function sendFirstMessage()
   {
      var _loc2_;
      if(lol.core.SceneShifter.firstGame)
      {
         _loc2_ = "Кажется, человек с восклицательным знаком над головой хочет Вам что-то сказать. Подойдите к нему и поговорите. Для этого кликните на его фигуру или восклицательный знак над головой";
         this.chat.systemMessage(0,"Подсказка",_loc2_);
         lol.core.SceneShifter.newStartGameHelpMessage();
      }
   }
}

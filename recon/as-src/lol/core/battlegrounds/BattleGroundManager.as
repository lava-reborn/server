class lol.core.battlegrounds.BattleGroundManager
{
   var BG_Operation;
   var BG_Par;
   var BG_Size;
   var BG_Status;
   var BG_Type;
   var HTTP;
   var XMC;
   var _debugtimerForStatistic;
   var bg_results;
   var currentSizes;
   var currentTypes;
   var dispatchEvent;
   var timerLoadDescr;
   var win_TeamID;
   var xmlArr;
   var xmlInfoLoaded;
   static var sBGMInstance;
   static var singleBGMCreation;
   static var BG_OPERATION_QUEUING = 0;
   static var BG_OPERATION_QUEUE_PARTY = 1;
   static var BG_OPERATION_EXIT_QUEUE = 2;
   static var BG_OPERATION_SAY_YES = 3;
   static var BG_OPERATION_SAY_NO = 4;
   static var BG_OPERATION_EXIT_INCOMPLETE_BG = 5;
   static var BG_OPERATION_GET_BG_INFO = 6;
   static var BG_OPERATION_EXIT_COMPLETED_BG = 7;
   static var BG_EVENT_BG_ANSWER = "BattleGround_Answer";
   static var BG_EVENT_SERVER_INVITE_US = "ServerInviteUs";
   static var BG_EVENT_GOT_STATISTIC = "BG_GotStatistic";
   static var BG_EVENT_PREPARE_TIME = "BG_PrepareTime";
   static var BG_SERVER_INVITE_US = 0;
   static var BG_SERVER_LAST_TIME = 1;
   static var BG_SERVER_BG_IN_PROGRESS = 2;
   static var BG_CLIENT_STATUS_IDLE = 0;
   static var BG_CLIENT_STATUS_QUEUE = 1;
   static var BG_CLIENT_STATUS_INVITED = 2;
   static var BG_CLIENT_STATUS_ON_INCOMPLETE_BG = 3;
   static var BG_CLIENT_STATUS_ON_COMPLETE_BG = 4;
   function BattleGroundManager()
   {
      if(lol.core.battlegrounds.BattleGroundManager.singleBGMCreation)
      {
         this.init();
      }
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("bg_init",this);
      this.XMC.addEventListener("bg_op",this);
      this.XMC.addEventListener("bg_res",this);
      this.currentTypes = new Array();
      this.currentSizes = new Array();
      this.bg_results = new Array();
      this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE;
      this.timerLoadDescr = setInterval(this,"loadDescription",3000);
   }
   function emulateStatistic()
   {
      clearInterval(this._debugtimerForStatistic);
      var _loc2_ = new Object();
      _loc2_.param = new Object();
      _loc2_.param.team_win = 0;
      _loc2_.param.players_0 = new Array();
      _loc2_.param.players_0.push(0);
      _loc2_.param.players_0.push(602);
      _loc2_.param.players_0.push(603);
      _loc2_.param.kills_0 = new Array();
      _loc2_.param.kills_0.push(5);
      _loc2_.param.kills_0.push(15);
      _loc2_.param.kills_0.push(25);
      _loc2_.param.deaths_0 = new Array();
      _loc2_.param.deaths_0.push(1);
      _loc2_.param.deaths_0.push(2);
      _loc2_.param.deaths_0.push(3);
      _loc2_.param.players_1 = new Array();
      _loc2_.param.players_1.push(604);
      _loc2_.param.players_1.push(605);
      _loc2_.param.players_1.push(606);
      _loc2_.param.kills_1 = new Array();
      _loc2_.param.kills_1.push(5);
      _loc2_.param.kills_1.push(14);
      _loc2_.param.kills_1.push(24);
      _loc2_.param.deaths_1 = new Array();
      _loc2_.param.deaths_1.push(5);
      _loc2_.param.deaths_1.push(6);
      _loc2_.param.deaths_1.push(7);
      this.bg_res(_loc2_);
   }
   function exitFromQueue()
   {
      var _loc2_;
      if(this.BG_Type != undefined && this.BG_Size != undefined)
      {
         _loc2_ = new lol.server.mess.CSM_BG_op(this.BG_Type,this.BG_Size,lol.core.battlegrounds.BattleGroundManager.BG_OPERATION_EXIT_QUEUE);
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.exitFromQueueAck);
         }
      }
   }
   function exitFromQueueAck(resObj)
   {
      this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE;
      var _loc2_ = resObj.param.res;
      if(_loc2_ != 0)
      {
         trace("exitFromQueueAck -> res != 0");
      }
   }
   function exitFromBattleGround(bg_is_complete)
   {
      var _loc2_ = bg_is_complete != true ? lol.core.battlegrounds.BattleGroundManager.BG_OPERATION_EXIT_INCOMPLETE_BG : lol.core.battlegrounds.BattleGroundManager.BG_OPERATION_EXIT_COMPLETED_BG;
      this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE;
      var _loc3_;
      if(this.BG_Type != undefined && this.BG_Size != undefined)
      {
         _loc3_ = new lol.server.mess.CSM_BG_op(this.BG_Type,this.BG_Size,_loc2_);
         this.XMC.Send(_loc3_);
      }
   }
   function requestingBGInfo()
   {
      var _loc2_;
      if(this.BG_Type != undefined && this.BG_Size != undefined)
      {
         _loc2_ = new lol.server.mess.CSM_BG_op(this.BG_Type,this.BG_Size,lol.core.battlegrounds.BattleGroundManager.BG_OPERATION_GET_BG_INFO);
         this.XMC.Send(_loc2_);
      }
   }
   function kill()
   {
      this.XMC.removeEventListener("bg_res",this);
      this.XMC.removeEventListener("bg_init",this);
      this.XMC.removeEventListener("bg_op",this);
   }
   static function getInstance()
   {
      if(!lol.core.battlegrounds.BattleGroundManager.sBGMInstance)
      {
         lol.core.battlegrounds.BattleGroundManager.singleBGMCreation = true;
         lol.core.battlegrounds.BattleGroundManager.sBGMInstance = new lol.core.battlegrounds.BattleGroundManager();
         lol.core.battlegrounds.BattleGroundManager.singleBGMCreation = false;
      }
      return lol.core.battlegrounds.BattleGroundManager.sBGMInstance;
   }
   function bg_init_emulation()
   {
      this.currentTypes.push(1);
      this.currentTypes.push(0);
      this.currentSizes.push(5);
      this.currentSizes.push(3);
      this.currentSizes.push(2);
      this.currentSizes.push(1);
   }
   function sortOnKillsAndDeaths(a, b)
   {
      if(a.kills > b.kills)
      {
         return -1;
      }
      if(a.kills < b.kills)
      {
         return 1;
      }
      if(a.deaths < b.deaths)
      {
         return -1;
      }
      if(a.deaths > b.deaths)
      {
         return 1;
      }
      return 0;
   }
   function bg_res(obj)
   {
      this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_ON_COMPLETE_BG;
      this.win_TeamID = obj.param.team_win;
      this.bg_results.splice(0,this.bg_results.length);
      var _loc3_ = 0;
      while(_loc3_ < obj.param.players_0.length)
      {
         this.bg_results.push({team_id:0,player_id:obj.param.players_0[_loc3_],kills:obj.param.kills_0[_loc3_],deaths:obj.param.deaths_0[_loc3_]});
         _loc3_ = _loc3_ + 1;
      }
      _loc3_ = 0;
      while(_loc3_ < obj.param.players_1.length)
      {
         this.bg_results.push({team_id:1,player_id:obj.param.players_1[_loc3_],kills:obj.param.kills_1[_loc3_],deaths:obj.param.deaths_1[_loc3_]});
         _loc3_ = _loc3_ + 1;
      }
      this.bg_results.sort(this.sortOnKillsAndDeaths);
      this.dispatchEvent({type:lol.core.battlegrounds.BattleGroundManager.BG_EVENT_GOT_STATISTIC});
   }
   function bg_init(obj)
   {
      this.currentTypes = obj.param.type_list;
      this.currentSizes = obj.param.ts_list;
      var _loc3_ = 0;
      var _loc2_ = 1;
      while(_loc3_ < this.currentTypes.length)
      {
         while(_loc2_ < this.currentTypes.length)
         {
            if(this.currentTypes[_loc3_] == this.currentTypes[_loc2_])
            {
               this.currentTypes.splice(_loc2_,1);
            }
            else
            {
               _loc2_ = _loc2_ + 1;
            }
         }
         _loc3_ = _loc3_ + 1;
      }
      this.currentSizes.sort();
   }
   function bg_op(obj)
   {
      this.BG_Type = obj.param.type;
      this.BG_Size = obj.param.ts;
      this.BG_Operation = obj.param.op;
      this.BG_Par = obj.param.par;
      if(this.BG_Type != undefined && !isNaN(this.BG_Type) && this.BG_Size != undefined && !isNaN(this.BG_Size) && this.BG_Operation != undefined && !isNaN(this.BG_Operation))
      {
         switch(this.BG_Operation)
         {
            case lol.core.battlegrounds.BattleGroundManager.BG_SERVER_INVITE_US:
               this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_INVITED;
               this.dispatchEvent({type:lol.core.battlegrounds.BattleGroundManager.BG_EVENT_SERVER_INVITE_US});
               break;
            case lol.core.battlegrounds.BattleGroundManager.BG_SERVER_LAST_TIME:
               if(this.BG_Par != undefined && !isNaN(this.BG_Par))
               {
                  this.dispatchEvent({type:lol.core.battlegrounds.BattleGroundManager.BG_EVENT_PREPARE_TIME,data:this.BG_Par});
               }
               break;
            case lol.core.battlegrounds.BattleGroundManager.BG_SERVER_BG_IN_PROGRESS:
               this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_ON_INCOMPLETE_BG;
            default:
               return;
         }
      }
   }
   function loadDescription()
   {
      clearInterval(this.timerLoadDescr);
      lol.core.SceneShifter._ref.initBGManagerListeners();
      this.xmlInfoLoaded = false;
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      this.HTTP.addEventListener("failed",this,this.descrFailed);
      var _loc2_ = lol.services.SSEmulator.getBG_DescURL();
      this.HTTP.Send("",_loc2_);
   }
   function onXML(obj)
   {
      this.xmlInfoLoaded = true;
      this.parse(obj.data);
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.removeEventListener("failed",this,this.descrFailed);
      this.HTTP.kill();
      this.HTTP = null;
   }
   function descrFailed(obj)
   {
      trace("BattleGroundManager -> descrFailed -> failed");
   }
   function parse(doc)
   {
      trace("BattleGroundManager -> parse");
      this.xmlArr = new Array();
      var _loc5_ = doc.firstChild.childNodes;
      var _loc3_;
      var _loc4_;
      var _loc2_;
      for(var _loc7_ in _loc5_)
      {
         _loc3_ = new Object();
         _loc3_ = _loc5_[_loc7_].attributes;
         _loc4_ = new Array();
         _loc2_ = _loc5_[_loc7_].childNodes;
         for(var _loc6_ in _loc2_)
         {
            _loc4_.push(_loc2_[_loc6_].childNodes[0]);
         }
         _loc3_.arr = _loc4_;
         this.xmlArr["bg" + _loc5_[_loc7_].attributes.id] = _loc3_;
      }
   }
   function getNameBG_ByTypeID(type)
   {
      trace("getNameBG_ByTypeID, type = " + type);
      trace("xmlArr.length = " + this.xmlArr.length);
      for(var _loc3_ in this.xmlArr)
      {
         trace("xmlArr[i].id = " + this.xmlArr[_loc3_].id);
         if(this.xmlArr[_loc3_].id == type)
         {
            return this.xmlArr[_loc3_].title;
         }
      }
   }
   function SayAnswerToServer(gotoBG)
   {
      var _loc2_;
      if(gotoBG == true)
      {
         _loc2_ = lol.core.battlegrounds.BattleGroundManager.BG_OPERATION_SAY_YES;
         this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_ON_INCOMPLETE_BG;
      }
      else
      {
         _loc2_ = lol.core.battlegrounds.BattleGroundManager.BG_OPERATION_SAY_NO;
         this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE;
      }
      var _loc3_ = new lol.server.mess.CSM_BG_op(this.BG_Type,this.BG_Size,_loc2_);
      this.XMC.Send(_loc3_);
   }
   function getDescBG_ByTypeID(type)
   {
      trace("getDescBG_ByTypeID, type = " + type);
      trace("xmlArr.length = " + this.xmlArr.length);
      for(var _loc3_ in this.xmlArr)
      {
         trace("xmlArr[i].id = " + this.xmlArr[_loc3_].id);
         if(this.xmlArr[_loc3_].id == type)
         {
            return this.xmlArr[_loc3_].description;
         }
      }
   }
   function goToBattleGround(type, size)
   {
      trace("goToBattleGround(" + type + ", " + size + ")");
      this.BG_Type = type;
      this.BG_Size = size;
      var _loc3_ = new lol.server.mess.CSM_BG_op(type,size,0);
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.bgJoinCmdAck);
      }
   }
   function bgJoinCmdAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      if(_loc2_ == 0)
      {
         this.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_QUEUE;
      }
      this.dispatchEvent({type:lol.core.battlegrounds.BattleGroundManager.BG_EVENT_BG_ANSWER,res:resObj.param.res});
   }
}

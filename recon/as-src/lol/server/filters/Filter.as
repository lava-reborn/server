class lol.server.filters.Filter
{
   var messArr;
   static var ADMIT = "admit";
   static var APPLY = "apply";
   static var HEAD = "head";
   static var CHWORLD = "chWorld";
   static var USERMSG = "userMsg";
   static var NEWPERS = "newPers";
   static var INSMARK = "insMark";
   static var MOVETO = "moveTo";
   static var RMMARK = "rmMark";
   static var UPDMARK = "updMark";
   static var HELLO = "hello";
   static var LENTER = "lenter";
   static var LOGIN = "login";
   static var LOGOUT = "logout";
   static var GETINFO = "getInfo";
   static var Q_CA = "q_ca";
   static var Q_LIST = "q_list";
   static var Q_DI = "q_di";
   static var Q_ST = "q_st";
   static var Q_SI = "q_si";
   static var Q_STATUS = "q_status";
   static var Q_CO = "q_co";
   static var RESURRECT = "resurrect";
   static var RP_GET_INFO = "rp_get_info";
   static var SELPERS = "selPers";
   static var SS_CREATE = "ss_create";
   static var SS_GET = "ss_get";
   static var SS_GET_DI = "ss_get_di";
   static var SS_GET_SI = "ss_get_si";
   static var CSM_P_OP = "p_op";
   static var E_GET_SI = "e_get_si";
   static var E_GET_DI = "e_get_di";
   static var BG_OP = "bg_op";
   static var SS_HEAP_C = "ss_heap_c";
   static var SS_MOVE = "ss_move";
   static var SS_UPD = "ss_upd";
   static var SS_USE = "ss_use";
   static var GG_INFO = "gg_info";
   static var ACTIVATE_PERS = "actPlayer";
   static var CONV = "on_conv";
   static var C_GA = "c_ga";
   static var M_CHECK_MAIL_PARAM = "chkml";
   static var M_GET_MAIL = "getml";
   static var M_REMOVE_MAIL = "rmvml";
   static var M_SEND_MAIL = "sndml";
   static var M_GET_ITEMS = "uldml";
   static var TR_GET_SI = "ts_get_si";
   static var SS_GET_S_SI = "ss_get_s_si";
   static var AH_CREATE = "ah_create";
   static var AH_OP = "ah_op";
   static var AH_SEARCH = "ah_search";
   static var DEFAULT = "default";
   function Filter()
   {
      this.messArr = new Array();
      this.messArr[lol.server.filters.Filter.HELLO] = true;
      this.messArr[lol.server.filters.Filter.LOGIN] = true;
      this.messArr[lol.server.filters.Filter.NEWPERS] = true;
      this.messArr[lol.server.filters.Filter.SELPERS] = true;
      this.messArr[lol.server.filters.Filter.ACTIVATE_PERS] = true;
      this.messArr[lol.server.filters.Filter.ADMIT] = true;
      this.messArr[lol.server.filters.Filter.APPLY] = true;
      this.messArr[lol.server.filters.Filter.HEAD] = true;
      this.messArr[lol.server.filters.Filter.CHWORLD] = true;
      this.messArr[lol.server.filters.Filter.LENTER] = true;
      this.messArr[lol.server.filters.Filter.USERMSG] = true;
      this.messArr[lol.server.filters.Filter.INSMARK] = true;
      this.messArr[lol.server.filters.Filter.RMMARK] = true;
      this.messArr[lol.server.filters.Filter.UPDMARK] = true;
      this.messArr[lol.server.filters.Filter.MOVETO] = true;
      this.messArr[lol.server.filters.Filter.LOGOUT] = true;
      this.messArr[lol.server.filters.Filter.GETINFO] = true;
      this.messArr[lol.server.filters.Filter.SS_CREATE] = true;
      this.messArr[lol.server.filters.Filter.SS_GET] = true;
      this.messArr[lol.server.filters.Filter.SS_GET_DI] = true;
      this.messArr[lol.server.filters.Filter.SS_GET_SI] = true;
      this.messArr[lol.server.filters.Filter.SS_HEAP_C] = true;
      this.messArr[lol.server.filters.Filter.SS_MOVE] = true;
      this.messArr[lol.server.filters.Filter.SS_UPD] = true;
      this.messArr[lol.server.filters.Filter.SS_USE] = true;
      this.messArr[lol.server.filters.Filter.GG_INFO] = true;
      this.messArr[lol.server.filters.Filter.CONV] = true;
      this.messArr[lol.server.filters.Filter.TR_GET_SI] = true;
      this.messArr[lol.server.filters.Filter.SS_GET_S_SI] = true;
      this.messArr[lol.server.filters.Filter.E_GET_SI] = true;
      this.messArr[lol.server.filters.Filter.E_GET_DI] = true;
      this.messArr[lol.server.filters.Filter.BG_OP] = true;
      this.messArr[lol.server.filters.Filter.Q_CA] = true;
      this.messArr[lol.server.filters.Filter.Q_LIST] = true;
      this.messArr[lol.server.filters.Filter.Q_DI] = true;
      this.messArr[lol.server.filters.Filter.Q_ST] = true;
      this.messArr[lol.server.filters.Filter.Q_SI] = true;
      this.messArr[lol.server.filters.Filter.Q_STATUS] = true;
      this.messArr[lol.server.filters.Filter.Q_CO] = true;
      this.messArr[lol.server.filters.Filter.CSM_P_OP] = true;
      this.messArr[lol.server.filters.Filter.RESURRECT] = true;
      this.messArr[lol.server.filters.Filter.C_GA] = true;
      this.messArr[lol.server.filters.Filter.RP_GET_INFO] = true;
      this.messArr[lol.server.filters.Filter.DEFAULT] = true;
      this.messArr[lol.server.filters.Filter.M_CHECK_MAIL_PARAM] = true;
      this.messArr[lol.server.filters.Filter.M_GET_ITEMS] = true;
      this.messArr[lol.server.filters.Filter.M_GET_MAIL] = true;
      this.messArr[lol.server.filters.Filter.M_REMOVE_MAIL] = true;
      this.messArr[lol.server.filters.Filter.M_SEND_MAIL] = true;
      this.messArr[lol.server.filters.Filter.AH_CREATE] = true;
      this.messArr[lol.server.filters.Filter.AH_OP] = true;
      this.messArr[lol.server.filters.Filter.AH_SEARCH] = true;
   }
   function setMask(messNames, flag)
   {
      var _loc2_;
      if(!messNames)
      {
         for(var _loc5_ in this.messArr)
         {
            _loc2_ = _loc5_;
            this.setFlag(_loc2_,flag);
         }
      }
      else
      {
         for(_loc5_ in this.messArr)
         {
            _loc2_ = _loc5_;
            this.setFlag(_loc2_,!flag);
         }
         for(_loc5_ in messNames)
         {
            _loc2_ = messNames[_loc5_];
            if(this.messArr[_loc2_] != undefined)
            {
               this.setFlag(_loc2_,flag);
            }
         }
      }
      this.messArr[lol.server.filters.Filter.DEFAULT] = true;
   }
   function setFlag(messName, flag)
   {
      this.messArr[messName] = flag;
   }
   function getFlag(messName)
   {
      return this.messArr[messName];
   }
}

class lol.utils.ErrorReport
{
   var XMC;
   var event;
   var paramName;
   var reportList;
   static var ERList;
   function ErrorReport(evt, pname)
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.event = evt;
      this.paramName = !pname ? "res" : pname;
      this.XMC.addEventListener(this.event,this,this.reportError);
      this.reportList = new Array();
   }
   function addReport(num, reportText, type)
   {
      var _loc3_ = !type ? "center" : type;
      this.reportList[num] = {text:reportText,viewType:_loc3_};
   }
   static function callReport(a, b)
   {
      var _loc1_ = lol.utils.ErrorReport.ERList[a];
      _loc1_.reportError({param:{res:b}});
   }
   function reportError(obj)
   {
      var _loc3_ = Number(obj.param[this.paramName]);
      var _loc2_ = this.reportList[_loc3_].text;
      var _loc6_ = this.reportList[_loc3_].viewType;
      if(_loc3_ == 27)
      {
         lol.core.SceneShifter._ref.currentScene.checkBagOverload();
      }
      var _loc7_;
      var _loc4_;
      var _loc5_;
      var _loc8_;
      if(_loc2_ && _loc2_.length > 0)
      {
         if(_loc6_ == "center")
         {
            _loc7_ = lol.core.SceneShifter.openNewWindow("alert","center");
            _loc7_.content.write(_loc2_);
         }
         else
         {
            _loc4_ = lol.core.SceneShifter.openNewAlert("topSimple");
            _loc4_.label = _loc2_;
            _loc5_ = _loc2_.length <= 35 ? 2000 : _loc2_.length * 70;
            _loc8_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,_loc5_,"topQuery");
         }
      }
   }
   static function create()
   {
      lol.utils.ErrorReport.ERList = new Array();
      lol.utils.ErrorReport.ERList[0] = new lol.utils.ErrorReport("cmdAck");
      lol.utils.ErrorReport.ERList[0].addReport(1,"некорректный логин или пароль");
      lol.utils.ErrorReport.ERList[0].addReport(2,"Аккаунт забанен");
      lol.utils.ErrorReport.ERList[0].addReport(3,"Сервер не отвечает","up");
      lol.utils.ErrorReport.ERList[0].addReport(4,"Аккаунт уже используется");
      lol.utils.ErrorReport.ERList[0].addReport(5,"Имя содержит некорректные символы");
      lol.utils.ErrorReport.ERList[0].addReport(6,"Имя уже используется другим аккаунтом");
      lol.utils.ErrorReport.ERList[0].addReport(7,"Невозможно перейти в локацию.");
      lol.utils.ErrorReport.ERList[0].addReport(8,"Невозможно пройти","up");
      lol.utils.ErrorReport.ERList[0].addReport(11,"Не хватает очков действия","up");
      lol.utils.ErrorReport.ERList[0].addReport(12,"Объект не найден","up");
      lol.utils.ErrorReport.ERList[0].addReport(13,"Кончились патроны","up");
      lol.utils.ErrorReport.ERList[0].addReport(14,"Патроны не подходят к этому оружию","up");
      lol.utils.ErrorReport.ERList[0].addReport(15,"Оружие уже заряжено","up");
      lol.utils.ErrorReport.ERList[0].addReport(16,"Предмет сломан","up");
      lol.utils.ErrorReport.ERList[0].addReport(17,"Объект не готов","up");
      lol.utils.ErrorReport.ERList[0].addReport(18,"Невозможно войти в локацию","up");
      lol.utils.ErrorReport.ERList[0].addReport(19,"Нет подходящего предмета","up");
      lol.utils.ErrorReport.ERList[0].addReport(27,"Вы перегружены","up");
      lol.utils.ErrorReport.ERList[0].addReport(44,"Вы сдали максимальное количество ежедневных квестов за один день","up");
      lol.utils.ErrorReport.ERList[0].addReport(45,"У вас не хватает навыков для использования этого предмета.","up");
      lol.utils.ErrorReport.ERList[0].addReport(1001,"Нельзя отправлять неадресное сообщение в приватный канал","up");
      lol.utils.ErrorReport.ERList[0].addReport(1002,"У вас должен быть вид на жительство","up");
      lol.utils.ErrorReport.ERList[0].addReport(1003,"У вас должно быть гражданство","up");
   }
}
